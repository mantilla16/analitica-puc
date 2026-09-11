"""
Lectura de Excel para el cargador de auditoría.

Dos operaciones:
  inspeccionar(ruta)          -> hojas, fila de encabezado y columnas detectadas
  parsear(ruta, perfil, nat)  -> filas normalizadas al esquema canónico

Regla central: los encabezados se localizan POR NOMBRE en cada archivo.
Nunca se guardan posiciones de columna, porque el mismo cliente exporta
con una columna A vacía en un periodo y sin ella en otro.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

MAX_FILAS_ESCANEO = 30
MIN_CELDAS_ENCABEZADO = 4

# Un .xlsx declara en `<dimension ref="...">` qué rango usa, y openpyxl en
# modo read_only le CREE: `iter_rows` recorta cada fila a la última columna
# declarada. Varios ERP escriben ese rango mal -- el movimiento auxiliar de
# DOXA declara `A1:A27591` teniendo 16 columnas -- y el efecto es que el
# archivo llega con una sola columna: sin encabezado que reconocer, o peor,
# con la primera columna buena y las demás en blanco. Es la forma más pura
# del error silencioso: el archivo miente sobre su propia forma y nada lo
# contradice.
#
# La salida está en la misma línea de openpyxl que causa el problema
# (`max_col = max_col or self.max_column`): pasando el ancho explícito, la
# dimensión declarada deja de consultarse. Se leen 64 columnas -- las que no
# existen vuelven como None, que es lo que ya se ignora -- y se compara
# contra lo declarado para poder decirlo.
MAX_COLUMNAS = 64


def _filas(ws, min_row: int = 1, max_row: int | None = None):
    """`iter_rows` sin creerle la dimensión que declara el archivo."""
    return ws.iter_rows(min_row=min_row, max_row=max_row,
                        max_col=MAX_COLUMNAS, values_only=True)


def _dimension_declarada(ws) -> tuple[int, int]:
    """(filas, columnas) según el propio archivo. 0 si no lo declara."""
    return (ws.max_row or 0), (ws.max_column or 0)

TOKENS_TRUE = {"si", "s", "x", "1", "true", "verdadero", "sí"}

PREFIJOS_DESCARTE = (
    "cuenta contable:",
    "total general",
    "total ",
    "procesado en:",
    "subtotal",
)


# --------------------------------------------------------------------- utils

def norm(s: Any) -> str:
    """Normaliza para comparar encabezados: minúsculas, sin tildes ni signos."""
    if s is None:
        return ""
    t = unicodedata.normalize("NFKD", str(s))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-zA-Z0-9 ]", " ", t).lower()
    return re.sub(r"\s+", " ", t).strip()


def sha256_archivo(ruta: str | Path, bloque: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while chunk := f.read(bloque):
            h.update(chunk)
    return h.hexdigest()


def a_numero(v: Any) -> str | None:
    """Devuelve un decimal en texto plano, o None si no es interpretable."""
    if v is None:
        return None
    if isinstance(v, (int, float, Decimal)):
        return f"{Decimal(str(v)):f}"

    s = str(v).strip()
    if not s or s == "-":
        return None

    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1].strip()

    s = re.sub(r"[^0-9.,+-]", "", s)
    signos = s.count("-") + s.count("+")
    if signos > 1:
        return None
    if signos == 1 and not (s[0] in "+-" or s[-1] in "+-"):
        return None          # signo en medio: '1-2' es basura, no un número
    if s.startswith("-") or s.endswith("-"):
        neg = True
    s = s.replace("+", "").replace("-", "")

    tiene_pto, tiene_com = "." in s, "," in s
    if tiene_pto and tiene_com:
        # el separador más a la derecha es el decimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif tiene_com:
        # 1 o 2 dígitos a la derecha y una sola coma => decimal
        if s.count(",") == 1 and len(s) - s.rfind(",") - 1 <= 2:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    elif tiene_pto:
        if not (s.count(".") == 1 and len(s) - s.rfind(".") - 1 <= 2):
            s = s.replace(".", "")

    if not re.fullmatch(r"[0-9]*\.?[0-9]*", s) or s in ("", "."):
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return f"{-d:f}" if neg else f"{d:f}"


def a_fecha(v: Any, formato: str = "DD/MM/YYYY") -> str | None:
    """Normaliza a ISO YYYY-MM-DD. El resto del sistema asume ISO."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()

    s = str(v).strip()
    if not s:
        return None

    patrones = {
        "DD/MM/YYYY": "%d/%m/%Y",
        "MM/DD/YYYY": "%m/%d/%Y",
        "YYYY-MM-DD": "%Y-%m-%d",
        "DD-MM-YYYY": "%d-%m-%Y",
    }
    orden = [patrones.get(formato, "%d/%m/%Y")] + list(patrones.values())
    for p in orden:
        try:
            return datetime.strptime(s[:10], p).date().isoformat()
        except ValueError:
            continue
    return None


def a_booleano(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return norm(v) in TOKENS_TRUE


# ------------------------------------------------------------- inspección

MAX_FILAS_BUSQUEDA_ADICIONAL = 3
MAX_FILAS_HASTA_DATOS = 6


def _es_fila_datos(fila: tuple) -> bool:
    """Heurística: una fila es de datos si la columna 0 tiene solo dígitos
    (código de cuenta contable). Los encabezados nunca son puros numéricos."""
    if not fila:
        return False
    v0 = fila[0]
    if v0 is None:
        return False
    s = str(v0).strip()
    return bool(s) and s.isdigit()


def _columnas_con_datos(ws, desde: int, filas: int = 15) -> set[int]:
    """Qué columnas traen algo debajo del encabezado.

    Es la única forma honesta de saber que una columna existe cuando el
    archivo no la rotula: se mira el dato, no el título.
    """
    vistas: set[int] = set()
    for fila in _filas(ws, min_row=desde, max_row=desde + filas - 1):
        for j, v in enumerate(fila or ()):
            if v is not None and str(v).strip():
                vistas.add(j)
    return vistas


def _detectar_encabezado(ws) -> tuple[int | None, list[dict]]:
    """Fila con más celdas de texto: es el encabezado. Devuelve (fila, columnas).

    Dos cosas que ningún archivo real respeta y hay que absorber aquí:

    · Los encabezados pueden estar repartidos en varias filas. Si en las
      filas siguientes aparece un texto sobre una columna que la fila
      principal dejó vacía, es el rótulo de esa columna y se agrega.

    · Puede haber columnas CON DATOS y SIN rótulo. El balance de SIESA pone
      el nombre de la cuenta en la columna B y escribe "Descripción" en la
      celda A13, indentada con espacios para que visualmente quede encima
      de B. Para quien lee el Excel se ve bien; para quien lo parsea, la
      columna B no tiene encabezado y desaparece del mapeo -- que fue
      exactamente lo que pasó: el nombre de la cuenta salía vacío.

      Esas columnas se ofrecen igual, nombradas por su letra ("Columna B").
      El nombre es estable entre cargas, que es lo que necesita el perfil
      guardado; adivinar el rótulo a partir de un texto suelto habría dado
      un nombre que cambia con el archivo.

    Lo que NO se hace: inventar índices. Antes, un rótulo que caía sobre una
    columna ya ocupada recibía un índice sintético negativo, y en Python
    `fila[-1]` no es "columna inexistente" sino la ÚLTIMA columna. Aquí
    devolvía None por casualidad; en otro archivo habría leído cifras de
    otra columna sin que nada lo advirtiera.
    """
    mejor_fila, mejor_puntaje, mejor_celdas = None, 0, []

    for i, fila in enumerate(_filas(ws, max_row=MAX_FILAS_ESCANEO), start=1):
        if not fila:
            continue
        celdas = [
            {"indice": j, "texto": str(v).strip()}
            for j, v in enumerate(fila)
            if v is not None and isinstance(v, str) and str(v).strip()
        ]
        if len(celdas) >= MIN_CELDAS_ENCABEZADO and len(celdas) > mejor_puntaje:
            mejor_fila, mejor_puntaje, mejor_celdas = i, len(celdas), celdas

    if mejor_fila is None:
        return None, []

    # --- rótulos repartidos en filas siguientes --------------------------
    ocupadas = {c["indice"] for c in mejor_celdas}
    primera_dato = mejor_fila + 1
    for num, fila in enumerate(
        _filas(ws, min_row=mejor_fila + 1,
               max_row=mejor_fila + MAX_FILAS_BUSQUEDA_ADICIONAL),
        start=mejor_fila + 1,
    ):
        if fila and _es_fila_datos(fila):
            primera_dato = num
            break
        primera_dato = num + 1
        for j, v in enumerate(fila or ()):
            if (v is not None and isinstance(v, str) and v.strip()
                    and j not in ocupadas):
                mejor_celdas.append({"indice": j, "texto": str(v).strip()})
                ocupadas.add(j)

    # --- columnas con datos que nadie rotuló ------------------------------
    for j in sorted(_columnas_con_datos(ws, primera_dato) - ocupadas):
        mejor_celdas.append({
            "indice": j,
            "texto": f"Columna {get_column_letter(j + 1)}",
            "sin_encabezado": True,
        })

    mejor_celdas.sort(key=lambda c: c["indice"])
    return mejor_fila, mejor_celdas


def inspeccionar(
    ruta: str | Path,
    sinonimos: set[str] | None = None,
    filas_muestra: int = 5,
) -> dict:
    """Estructura del archivo, sin aplicar ningún perfil.

    `sinonimos` son los encabezados conocidos del estándar, ya normalizados
    (core.campo_sinonimo.norm). Se usan para elegir la hoja: gana la que más
    encabezados reconocibles tenga.

    Sin ellos, contar columnas elegiría la hoja equivocada: los archivos de
    LIQUITECH traen una hoja "TRABAJADO" del auditor con MÁS columnas que
    la hoja buena.
    """
    sinonimos = sinonimos or set()
    wb = load_workbook(ruta, read_only=True, data_only=True)
    hojas = []

    for orden, nombre in enumerate(wb.sheetnames):
        ws = wb[nombre]
        fila_enc, columnas = _detectar_encabezado(ws)

        muestra = []
        if fila_enc:
            for fila in _filas(ws, min_row=fila_enc + 1,
                               max_row=fila_enc + filas_muestra):
                muestra.append([
                    None if v is None else str(v)[:60]
                    for v in (fila or ())
                ])

        reconocidos = sum(1 for c in columnas if norm(c["texto"]) in sinonimos)

        # Que el archivo mienta sobre su ancho no se calla: es un dato sobre
        # la fuente, y el auditor tiene que saber que lo leido no coincide
        # con lo que el archivo declara de si mismo.
        _, col_declaradas = _dimension_declarada(ws)
        col_reales = max((c["indice"] for c in columnas), default=-1) + 1
        for f in muestra:
            col_reales = max(col_reales,
                             max((j + 1 for j, v in enumerate(f)
                                  if v is not None), default=0))

        hojas.append({
            "hoja": nombre,
            "orden": orden,
            "fila_encabezado": fila_enc,
            "encabezados": [c["texto"] for c in columnas],
            "columnas": columnas,
            "reconocidos": reconocidos,
            "muestra": muestra,
            "columnas_declaradas": col_declaradas,
            "columnas_reales": col_reales,
            "dimension_mal_declarada": col_reales > col_declaradas > 0,
        })

    wb.close()

    candidatas = [h for h in hojas if h["fila_encabezado"]]
    if sinonimos:
        # más encabezados del estándar; a igualdad, la hoja que va primero
        sugerida = max(candidatas,
                       key=lambda h: (h["reconocidos"], -h["orden"]),
                       default=None)
    else:
        sugerida = candidatas[0] if candidatas else None

    return {
        "hojas": hojas,
        "hoja_sugerida": sugerida["hoja"] if sugerida else None,
    }


# ----------------------------------------------------------------- parseo

def _indices(columnas_perfil: dict[str, str], celdas: list[dict]) -> dict[str, int]:
    """campo canónico -> índice real de columna EN ESTE archivo."""
    por_norma = {norm(c["texto"]): c["indice"] for c in celdas}
    faltantes, idx = [], {}
    for campo, encabezado in columnas_perfil.items():
        if not encabezado:
            continue
        j = por_norma.get(norm(encabezado))
        if j is None:
            faltantes.append(f"{campo} -> '{encabezado}'")
        else:
            idx[campo] = j
    if faltantes:
        raise ValueError(
            "El archivo no contiene las columnas del perfil: " + "; ".join(faltantes)
        )
    return idx


def _descartable(codigo: Any) -> bool:
    if codigo is None:
        return True
    s = str(codigo).strip()
    if not s:
        return True
    n = s.lower()
    if any(n.startswith(p) for p in PREFIJOS_DESCARTE):
        return True
    return not s.isdigit()


NUMERICOS = {"saldo_inicial", "debito", "credito", "saldo_final"}


def parsear(ruta: str | Path, perfil: dict, naturaleza: str) -> Iterator[dict]:
    """Genera filas normalizadas. No carga el archivo entero en memoria."""
    columnas = perfil["columnas"]
    hoja_perfil = perfil.get("hoja")
    ignorar = {norm(h) for h in perfil.get("ignorar_hojas", [])}
    fmt_fecha = perfil.get("formato_fecha", "DD/MM/YYYY")

    wb = load_workbook(ruta, read_only=True, data_only=True)
    try:
        objetivo = [hoja_perfil] if hoja_perfil in wb.sheetnames else [
            h for h in wb.sheetnames if norm(h) not in ignorar
        ]

        for nombre in objetivo:
            ws = wb[nombre]
            fila_enc, celdas = _detectar_encabezado(ws)
            if not fila_enc:
                continue
            try:
                idx = _indices(columnas, celdas)
            except ValueError:
                if hoja_perfil:
                    raise
                continue          # hoja auxiliar sin los encabezados esperados

            # Separar índices reales de los sintéticos (negativos).
            # Los sintéticos corresponden a encabezados en filas adicionales
            # que no se pueden leer de la misma columna de datos (p. ej.
            # "Descripción" debajo de "Cuentas" en SIESA 2025).
            idx_real = {k: v for k, v in idx.items() if v >= 0}
            n_col = max(idx_real.values()) + 1 if idx_real else 0

            for n, fila in enumerate(_filas(ws, min_row=fila_enc + 1),
                                     start=fila_enc + 1):
                if not fila:
                    continue
                fila = tuple(fila) + (None,) * (n_col - len(fila))

                if "codigo_puc" in idx_real and _descartable(fila[idx_real["codigo_puc"]]):
                    continue

                out: dict[str, Any] = {"fila_origen": n, "hoja": nombre}
                for campo, j in idx.items():
                    if j < 0:
                        # índice sintético: el valor no está en esta fila
                        # (vino de una fila adicional durante la inspección)
                        out[campo] = None
                        continue
                    v = fila[j]
                    if campo in NUMERICOS:
                        out[campo] = a_numero(v)
                    elif campo == "fecha":
                        out[campo] = a_fecha(v, fmt_fecha)
                    elif campo == "transaccional":
                        out[campo] = "Si" if a_booleano(v) else "No"
                    else:
                        out[campo] = None if v is None else str(v).strip()

                yield out
    finally:
        wb.close()
