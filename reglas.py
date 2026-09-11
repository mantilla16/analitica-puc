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
    """Materialidad de ejecución y error trivial."""
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


# A qué fecha del encargo debe corresponder el cierre de cada insumo. Es
# la mitad de la derivación del periodo -- solo el final -- y con eso basta
# para saber si un archivo ya cargado dejó de corresponder al encargo.
FECHA_DEL_INSUMO = {
    "BAL_ACTUAL":          "fecha_corte",
    "MOV_ACTUAL":          "fecha_corte",
    "PRECOMPROBANTE":      "fecha_corte",
    "BAL_CIERRE_ANTERIOR": "fecha_cierre_anterior",
    "MOV_ANTERIOR":        "fecha_cierre_anterior",
    "BAL_CORTE_ANTERIOR":  "fecha_corte_anterior",
}


def desalineados(insumos, fechas: dict) -> list[dict]:
    """Qué insumos ya cargados dejarían de corresponder con estas fechas.

    Cambiar la fecha de corte de un encargo mueve los dos periodos
    comparativos, pero los archivos ya subidos conservan el periodo con el
    que entraron. Sin esta comprobación, el papel diría "corte a 30/06" sobre
    un balance de mayo: coherente, firmable y equivocado.

    Se compara solo el cierre del periodo porque es lo que identifica al
    insumo; el inicio se deriva de él.

    `insumos` son filas con `tipo` y `periodo_fin`; `fechas` es el encargo ya
    con los valores nuevos.
    """
    malos = []
    for i in insumos:
        campo = FECHA_DEL_INSUMO.get(i["tipo"])
        if not campo or i.get("periodo_fin") is None:
            continue
        esperada = fechas.get(campo)
        if esperada is not None and i["periodo_fin"] != esperada:
            malos.append({"tipo": i["tipo"], "tenia": i["periodo_fin"],
                          "deberia": esperada, "campo": campo})
    return malos


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


def origen_del_signo(codigo: str, excepciones: dict[str, str],
                     signo_clase: dict[str, int]) -> tuple[str, int, bool]:
    """Qué declaración resolvió la naturaleza de un código.

    `signo_de_codigo` devuelve el signo pero no de dónde salió, y para el
    papel esa procedencia es justo el dato que importa: una naturaleza
    declarada es una decisión tomada; una heredada de la clase es un supuesto,
    y de ese supuesto depende el signo con que la cuenta entra al comparativo.

    Devuelve (prefijo, signo, declarado).
    """
    for n in range(len(codigo), 0, -1):
        nat = excepciones.get(codigo[:n])
        if nat:
            return codigo[:n], (1 if nat == "D" else -1), True
    return codigo[:1], signo_clase.get(codigo[:1], 1), False


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


def convencion_signo(filas, signo_clase: dict[str, int]
                     ) -> tuple[str, dict[str, str]]:
    """Cómo trae el archivo los saldos: ¿en positivo, o ya con signo?

    No es un parámetro de configuración: es una pregunta con respuesta
    comprobable. Un balance completo suma cero, así que se prueban las dos
    hipótesis sobre las cuentas de CLASE y gana la que cuadra.

    · CATALOGO  -- el archivo trae todo en positivo (pasivos incluidos) y el
      signo hay que tomarlo del catálogo. Es lo que entrega LIQUITECH.
    · ARCHIVO   -- el archivo ya trae pasivos, patrimonio e ingresos en
      negativo, y sus clases suman cero tal cual. Es lo que entrega FGC.
    · INDETERMINADA -- ninguna cuadra. Se declara; no se elige la menos mala.

    Se mide sobre las clases (un dígito) porque es el nivel que siempre
    existe y el que menos filas tiene: si el árbol es consistente, cuadrar
    ahí equivale a cuadrar en cualquier nivel completo.

    Devuelve la convención y las dos sumas, para poder mostrarlas: una
    detección que no dice cuánto dio cada hipótesis no se puede auditar.
    """
    crudo = Decimal(0)
    con_signo = Decimal(0)
    clases = 0
    for f in filas:
        cod = (f.get("codigo_puc") or "").strip()
        if len(cod) != 1 or not cod.isdigit():
            continue
        clases += 1
        sf = Decimal(str(f.get("saldo_final") or 0))
        crudo += sf
        con_signo += sf * signo_clase.get(cod, 1)

    crudo = crudo.quantize(Decimal("0.01"))
    con_signo = con_signo.quantize(Decimal("0.01"))
    sumas = {"clases": clases, "suma_tal_cual": str(crudo),
             "suma_con_signo_del_catalogo": str(con_signo)}

    if not clases:
        return "INDETERMINADA", sumas
    # El orden importa cuando las dos cuadran, que pasa si el balance está
    # todo en cero: se prefiere CATALOGO por ser el comportamiento anterior,
    # y así un archivo vacío no cambia de convención de una carga a otra.
    if con_signo == 0:
        return "CATALOGO", sumas
    if crudo == 0:
        return "ARCHIVO", sumas
    return "INDETERMINADA", sumas


# ------------------------------------------------------ motivo de selección

MOTIVOS = ("Monto", "Cuenta nueva", "Cuenta cerrada", "Comportamiento",
           "Naturaleza")


def motivo_seleccion(sa: Decimal, sc: Decimal, var: Decimal,
                     pctv: Decimal | None, umbral: Decimal | None,
                     trivial: Decimal, pct_var: Decimal,
                     usa_var: bool,
                     naturaleza: Decimal | None = None) -> str | None:
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
    # `naturaleza` es el saldo frente al signo del CATÁLOGO, que no siempre
    # coincide con el saldo comparable: si el archivo ya trae los signos
    # aplicados, todo pasivo tiene saldo comparable negativo y usarlo aquí
    # marcaría como excepción lo que es normal. Cuando no se pasa, se cae al
    # saldo comparable, que es el comportamiento anterior.
    nat = sa if naturaleza is None else naturaleza
    if nat < 0 and abs(nat) >= trivial:
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


MONEY = ("saldo_inicial", "debito", "credito", "saldo_final")


def consolidar_duplicados(filas: list[dict]) -> tuple[list[dict], list[dict]]:
    """Un codigo repetido en el mismo balance, resuelto segun por que se repite.

    `core.balance` tiene UNIQUE (carga_id, codigo_puc), asi que un codigo
    repetido tumbaba el COPY entero y la carga quedaba SIN una sola fila --
    un 500 en la cara del auditor y cero balance. Callarse con
    ON CONFLICT DO NOTHING seria peor: se perderia un saldo sin decirlo.

    Hay dos causas y piden lo contrario:

    - **Linea duplicada** del export (todas las cifras iguales): es la misma
      fila impresa dos veces. Sumarla dobla la cuenta. Se conserva una.
    - **Codigo repartido** (cifras distintas: centros de costo, sucursales,
      terceros): el saldo de la cuenta es la suma. Se suma.

    Adivinar no es peligroso porque hay como comprobarlo: `cuadre_por_nivel`
    exige que cada nivel completo sume cero. Si se deduplica lo que habia
    que sumar, o se suma lo que habia que deduplicar, el nivel se descuadra
    y la carga se marca CON_HALLAZGOS. Cualquiera de los dos errores sale a
    la luz en vez de quedar como una cifra silenciosa.

    Devuelve las filas consolidadas -- en el orden de primera aparicion --
    y la lista de lo que se hizo, para que quede como hallazgo.
    """
    orden: list[str] = []
    grupos: dict[str, list[dict]] = {}
    for f in filas:
        cod = f["codigo_puc"]
        if cod not in grupos:
            grupos[cod] = []
            orden.append(cod)
        grupos[cod].append(f)

    salida, duplicados = [], []
    for cod in orden:
        g = grupos[cod]
        if len(g) == 1:
            salida.append(g[0])
            continue

        huella = {tuple(Decimal(str(f.get(k) or 0)) for k in MONEY) for f in g}
        base = dict(g[0])
        if len(huella) == 1:
            trato = "IDENTICA"
        else:
            trato = "SUMADA"
            for k in MONEY:
                base[k] = sum((Decimal(str(f.get(k) or 0)) for f in g), Decimal(0))
            signo = base.get("signo") or 1
            base["saldo_naturaleza"] = base["saldo_final"] * signo
            # `saldo_natural` puede venir sin signo aplicado (convencion del
            # archivo); se reconstruye con la misma proporcion que traia.
            base["saldo_natural"] = (base["saldo_final"] if g[0].get("saldo_natural") ==
                                     g[0].get("saldo_final")
                                     else base["saldo_final"] * signo)

        salida.append(base)
        duplicados.append({
            "codigo_puc": cod, "nombre_cuenta": base.get("nombre_cuenta"),
            "veces": len(g), "trato": trato,
            "saldo_final": base["saldo_final"],
        })

    return salida, duplicados


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
