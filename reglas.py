"""
Reglas de negocio. Todo lo que antes vivía en Postgres como funciones,
vistas y columnas generadas.

La base solo guarda tablas y llaves foráneas. Aquí está el resto.
"""
from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

# --------------------------------------------------------------- materialidad

FACTOR_ME_DEFECTO = Decimal("0.750")
FACTOR_CTT_DEFECTO = Decimal("0.050")
PCT_VARIACION_DEFECTO = Decimal("20.00")


def derivar_materialidad(
    mp: Decimal,
    factor_me: Decimal = FACTOR_ME_DEFECTO,
    factor_ctt: Decimal = FACTOR_CTT_DEFECTO,
) -> tuple[Decimal, Decimal]:
    """Materialidad de ejecución y umbral de trivialidad."""
    dos = Decimal("0.01")
    return (
        (mp * factor_me).quantize(dos),
        (mp * factor_ctt).quantize(dos),
    )


# -------------------------------------------------------------------- fechas

def derivar_fechas_encargo(fecha_corte: date) -> tuple[date, date]:
    """(cierre del año anterior, mismo corte del año anterior).

    Clases 1-3 se comparan contra el 31-dic anterior.
    Clases 4-7 contra el mismo corte del año pasado.
    """
    cierre = date(fecha_corte.year - 1, 12, 31)
    try:
        corte = date(fecha_corte.year - 1, fecha_corte.month, fecha_corte.day)
    except ValueError:                      # 29-feb en año no bisiesto
        corte = date(fecha_corte.year - 1, fecha_corte.month, 28)
    return cierre, corte


def inicio_periodo_auditado(fecha_corte: date) -> date:
    """Todo movimiento anterior a esta fecha está en periodo ya cerrado."""
    return date(fecha_corte.year, 1, 1)


# ---------------------------------------------------------------- naturaleza

def resolver_signo(codigo: str, excepciones: dict[str, str],
                   signo_clase: dict[str, int]) -> int:
    """Prefijo declarado más largo; si no hay, manda la clase.

    `excepciones` es {codigo: 'D'|'C'} de core.puc donde naturaleza no es NULL.
    Así 159205 resuelve a crédito porque 1592 está declarada, sin que nadie
    la haya registrado.
    """
    for n in range(len(codigo), 0, -1):
        nat = excepciones.get(codigo[:n])
        if nat:
            return 1 if nat == "D" else -1
    return signo_clase.get(codigo[:1], 1)


# --------------------------------------------------------------------- huella

def _h(*partes: str) -> str:
    return hashlib.sha256("|~|".join(partes).encode()).hexdigest()


def _n(v: Any) -> str:
    """El VALOR de una cifra, no su escritura.

    La huella se calculaba sobre el texto tal como salió del archivo, y ahí
    `37719.9` y `37719.90` son dos huellas distintas para el mismo peso.
    Consecuencia: reemplazar un archivo donde una celda pasó de texto a
    número -- o de 0 a 0.00, que Excel cambia solo al guardar -- marcaba la
    fila como MODIFICADA, y si el periodo ya estaba cerrado disparaba la
    alerta de "cambios en periodo ya auditado" sin que nadie hubiera tocado
    una cifra. Una alerta falsa que aparece sola es peor que ninguna: le
    enseña al auditor a ignorarlas.

    Se cuantiza a dos decimales porque es la precisión que el sistema
    conserva de staging en adelante (`numeric(19,2)`): comparar con más
    precisión de la que se guarda solo produce diferencias fantasma.
    """
    if v is None or v == "":
        return "0.00"
    try:
        return f"{Decimal(str(v)).quantize(Decimal('0.01')):f}"
    except (InvalidOperation, ValueError, ArithmeticError):
        return str(v)      # no es un número: se compara como texto


def llave_movimiento(f: dict) -> str:
    """Llave natural verificada en datos reales: única en 122.795 filas."""
    return _h(f.get("num_doc") or "", f.get("secuencia") or "",
              f.get("codigo_puc") or "")


def huella_movimiento(f: dict) -> str:
    return _h(f.get("num_doc") or "", f.get("secuencia") or "",
              f.get("codigo_puc") or "", f.get("fecha") or "",
              f.get("tercero_nit") or "", f.get("descripcion") or "",
              _n(f.get("debito")), _n(f.get("credito")))


def llave_balance(f: dict) -> str:
    return _h(f.get("codigo_puc") or "")


def huella_balance(f: dict) -> str:
    return _h(f.get("codigo_puc") or "", _n(f.get("saldo_inicial")),
              _n(f.get("debito")), _n(f.get("credito")),
              _n(f.get("saldo_final")))


def marcar_huellas(filas: Iterable[dict], naturaleza: str):
    kl = llave_movimiento if naturaleza == "MOVIMIENTO" else llave_balance
    kh = huella_movimiento if naturaleza == "MOVIMIENTO" else huella_balance
    for f in filas:
        f["llave"] = kl(f)
        f["huella"] = kh(f)
        yield f


# ------------------------------------------------------ motivo de selección

MOTIVOS = ("Monto", "Cuenta nueva", "Cuenta cerrada", "Comportamiento",
           "Naturaleza")


def motivo_seleccion(sa: Decimal, sc: Decimal, var: Decimal,
                     pctv: Decimal | None, umbral: Decimal | None,
                     trivial: Decimal, pct_var: Decimal,
                     usa_var: bool) -> str | None:
    """Por qué una cuenta entra al alcance, o None si no entra.

    Estaba dentro de `variaciones`, entre las consultas y el armado de la
    fila, donde no había forma de probarla sin base de datos. Es la decisión
    más importante del módulo -- define el alcance del trabajo -- así que
    vive aparte y se valida con casos sembrados.

    La cascada es `elif` a propósito: una cuenta se marca por UN motivo, el
    primero que aplica, en orden de fuerza. Si se marcara por varios, contar
    "cuántas por comportamiento" dejaría de sumar al total.
    """
    if umbral is None:
        return None                      # sin materialidad no se marca nada
    if abs(var) >= umbral:
        return "Monto"
    if sc == 0 and abs(sa) >= trivial:
        return "Cuenta nueva"
    if sa == 0 and abs(sc) >= trivial:
        return "Cuenta cerrada"
    if usa_var and pctv is not None and abs(pctv) >= pct_var and abs(var) >= trivial:
        return "Comportamiento"
    if sa < 0 and abs(sa) >= trivial:
        return "Naturaleza"
    return None


# ------------------------------------------------------------------- cotejo

def cotejar(nuevas: dict[str, str], previas: dict[str, str]) -> dict[str, list[str]]:
    """Compara dos conjuntos {llave: huella}.

    Devuelve las llaves clasificadas. Igual llave con distinta huella
    significa fila modificada.
    """
    kn, kp = set(nuevas), set(previas)
    return {
        "nuevas": sorted(kn - kp),
        "eliminadas": sorted(kp - kn),
        "modificadas": sorted(k for k in kn & kp if nuevas[k] != previas[k]),
    }


# -------------------------------------------------------------- validaciones

def validar_mapeo(mapeo: dict, campos: list[dict]) -> list[dict]:
    """Requeridos presentes, campos existentes, sin columnas repetidas."""
    cols = {k: v for k, v in (mapeo.get("columnas") or {}).items() if v}
    conocidos = {c["campo"] for c in campos}
    problemas: list[dict] = []

    for c in campos:
        if c["requerido"] and c["campo"] not in cols:
            problemas.append({
                "severidad": "ERROR",
                "problema": "Campo requerido sin relacionar",
                "detalle": f"{c['etiqueta']} ({c['campo']})",
            })

    for campo in cols:
        if campo not in conocidos:
            problemas.append({
                "severidad": "ERROR",
                "problema": "Campo no existe en el estándar",
                "detalle": campo,
            })

    invertido: dict[str, list[str]] = {}
    for campo, enc in cols.items():
        invertido.setdefault(enc, []).append(campo)
    for enc, campos_ in invertido.items():
        if len(campos_) > 1:
            problemas.append({
                "severidad": "ERROR",
                "problema": "Columna asignada a más de un campo",
                "detalle": f"{enc} -> {', '.join(campos_)}",
            })

    if "transaccional" not in cols and any(c["campo"] == "transaccional" for c in campos):
        problemas.append({
            "severidad": "AVISO",
            "problema": "Sin columna de transaccionalidad",
            "detalle": "No es crítico: el nivel se deriva de la longitud del código.",
        })
    if "descripcion" not in cols and any(c["campo"] == "descripcion" for c in campos):
        problemas.append({
            "severidad": "AVISO",
            "problema": "Sin columna de descripción",
            "detalle": "No se podrán agrupar patrones de movimiento.",
        })

    return problemas


def cuadre_por_nivel(filas: list[dict], niveles: dict[str, dict]) -> list[dict]:
    """Cada nivel completo debe sumar cero. Es la ecuación contable.

    Auxiliar no cuadra solo: hay subcuentas que no bajan a 8 dígitos.
    """
    agr: dict[str, dict] = {}
    for f in filas:
        n = f["nivel"]
        a = agr.setdefault(n, {"nivel": n, "filas": 0,
                               "suma_saldo_final": Decimal(0),
                               "debito": Decimal(0), "credito": Decimal(0)})
        a["filas"] += 1
        a["suma_saldo_final"] += Decimal(str(f["saldo_final"]))
        a["debito"] += Decimal(str(f["debito"]))
        a["credito"] += Decimal(str(f["credito"]))

    salida = []
    for n, a in agr.items():
        completo = niveles.get(n, {}).get("nivel_completo", False)
        suma = a["suma_saldo_final"].quantize(Decimal("0.01"))
        salida.append({
            "nivel": n,
            "filas": a["filas"],
            "suma_saldo_final": suma,
            "descuadre_movimiento": (a["debito"] - a["credito"]).quantize(Decimal("0.01")),
            "nivel_completo": completo,
            "estado": "n/a" if not completo else ("OK" if suma == 0 else "DESCUADRE"),
        })
    salida.sort(key=lambda x: niveles.get(x["nivel"], {}).get("orden", 99))
    return salida


def cuadre_por_linea(filas: list[dict]) -> list[dict]:
    """saldo_inicial + debito - credito = saldo_final, fila por fila."""
    malas = []
    for f in filas:
        si, db, cr, sf = (Decimal(str(f.get(k) or 0))
                          for k in ("saldo_inicial", "debito", "credito", "saldo_final"))
        dif = (si + db - cr - sf).quantize(Decimal("0.01"))
        if dif != 0:
            malas.append({"codigo_puc": f["codigo_puc"], "diferencia": dif,
                          "fila_origen": f.get("fila_origen")})
    return malas
