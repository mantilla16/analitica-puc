"""
Validación del motor contra ground truth.

Un motor está "validado" solo cuando se comprueba que encuentra defectos que
alguien sembró a propósito. Antes de eso está corriendo, no validado -- y la
diferencia importa: los tres defectos que aparecieron el 1-sep-2026 (el
balance sin promover que pasaba silencioso, la huella que inventaba cambios,
la falta de tolerancia en el cruce) se encontraron mirando síntomas, no
porque una prueba los cazara.

Método, y el sentido importa: la fuente sintética se DERIVA del balance REAL
y se le siembran defectos conocidos. Al revés -- fabricar el dato de prueba
desde cero, o derivar el comparativo del mismo archivo que se verifica --
cuadra siempre y no prueba nada.

Cada caso declara qué sembró y qué espera. Hay casos NEGATIVOS: cosas que el
motor NO debe reportar. Un motor que encuentra todo lo sembrado pero además
inventa hallazgos es igual de inservible, solo que de la otra forma.

    python validar_motor.py

Sale con código 1 si algún caso falla, para poder encadenarlo en un
despliegue.
"""
from __future__ import annotations

import copy
import sys
from decimal import Decimal

import db
import reglas as R

D = Decimal
CENT = D("0.01")

resultados: list[tuple[bool, str, str]] = []


def caso(nombre: str, esperado, obtenido, nota: str = "") -> None:
    ok = esperado == obtenido
    resultados.append((ok, nombre,
                       nota if ok else f"esperaba {esperado}, obtuvo {obtenido}"))


def informar(nombre: str, nota: str) -> None:
    """Un dato observado, no una aserción. Se imprime para que quien corre la
    validación vea sobre qué corrió."""
    resultados.append((True, nombre, nota))


# =====================================================================
# BASE REAL
# =====================================================================

def base_real() -> list[dict]:
    """El balance actual del encargo, tal como está en core.

    Si no hay balance promovido no se inventa uno: validar contra datos
    fabricados desde cero probaría la aritmética, no el motor.
    """
    filas = db.varios(
        """SELECT b.codigo_puc, b.nombre_cuenta, b.nivel, b.clase,
                  b.saldo_inicial, b.debito, b.credito, b.saldo_final,
                  b.signo, b.saldo_natural
             FROM core.encargo_insumo ei
             JOIN core.balance b ON b.carga_id = ei.carga_id
            WHERE ei.tipo = 'BAL_ACTUAL'
            ORDER BY b.codigo_puc""")
    return [dict(f) for f in filas]


def numerar(filas: list[dict]) -> list[dict]:
    for i, f in enumerate(filas, start=2):
        f["fila_origen"] = i
    return filas


# =====================================================================
# CUADRE POR LÍNEA
# =====================================================================

def validar_cuadre_linea(base: list[dict]) -> None:
    """Se siembran descuadres en cuentas conocidas: deben salir todas, con la
    cifra exacta, y ninguna más."""
    limpio = [f for f in base if not R.cuadre_por_linea([f])]
    informar("cuadre por línea · base",
             f"{len(limpio)} de {len(base)} filas del balance real ya cuadran")
    if len(limpio) < 6:
        resultados.append((False, "cuadre por línea",
                           "el balance real no tiene 6 filas sanas para sembrar"))
        return

    caso("cuadre por línea · una base sana no reporta nada",
         0, len(R.cuadre_por_linea(limpio)))

    filas = copy.deepcopy(limpio)
    sembrados = {}
    for f, delta in zip(filas, ("0.01", "-1000", "999999999", "0.02", "-7")):
        f["saldo_final"] = D(str(f["saldo_final"])) + D(delta)
        sembrados[f["codigo_puc"]] = (-D(delta)).quantize(CENT)

    hallados = R.cuadre_por_linea(filas)
    caso("cuadre por línea · encuentra los 5 sembrados",
         sorted(sembrados), sorted(h["codigo_puc"] for h in hallados))
    caso("cuadre por línea · la diferencia es exacta",
         sembrados, {h["codigo_puc"]: h["diferencia"] for h in hallados})

    # NEGATIVO: mover un centavo del débito al saldo final no descuadra nada
    compensado = copy.deepcopy(limpio)
    compensado[0]["debito"] = D(str(compensado[0]["debito"])) + CENT
    compensado[0]["saldo_final"] = D(str(compensado[0]["saldo_final"])) + CENT
    caso("cuadre por línea · un movimiento compensado NO se reporta",
         0, len(R.cuadre_por_linea(compensado)))


# =====================================================================
# CUADRE POR NIVEL
# =====================================================================

def validar_cuadre_nivel(base: list[dict]) -> None:
    niveles = {n["nivel"]: n for n in db.varios(
        "SELECT nivel, nivel_completo, orden FROM core.nivel_cargable")}
    cuadre = {q["nivel"]: q for q in R.cuadre_por_nivel(base, niveles)}
    informar("cuadre por nivel · base",
             ", ".join(f"{n}={q['estado']}" for n, q in cuadre.items()))

    completos = [n for n, q in cuadre.items()
                 if q["nivel_completo"] and q["estado"] == "OK"]
    if not completos:
        resultados.append((False, "cuadre por nivel",
                           "ningún nivel completo del balance real cuadra, "
                           "así que no hay base sana para sembrar"))
        return

    nivel = completos[0]
    filas = copy.deepcopy(base)
    for f in filas:
        if f["nivel"] == nivel:
            f["saldo_final"] = D(str(f["saldo_final"])) + D("1000000")
            break
    roto = {q["nivel"]: q for q in R.cuadre_por_nivel(filas, niveles)}

    caso(f"cuadre por nivel · un millón sembrado descuadra {nivel}",
         "DESCUADRE", roto[nivel]["estado"])
    caso("cuadre por nivel · los demás niveles no se contagian",
         {n: q["estado"] for n, q in cuadre.items() if n != nivel},
         {n: q["estado"] for n, q in roto.items() if n != nivel})


# =====================================================================
# HUELLA
# =====================================================================

def validar_huellas(base: list[dict]) -> None:
    """La huella debe reaccionar al VALOR y ser ciega a la escritura. Las dos
    mitades importan: sin la primera no detecta cambios, sin la segunda
    inventa cambios que nadie hizo."""
    real = dict(base[0])
    sf = D(str(real["saldo_final"]))

    escrituras = (
        ("dos decimales contra cuatro", "saldo_final",
         f"{sf:.2f}", f"{sf:.4f}"),
        ("cero escrito '0' contra '0.00'", "debito", "0", "0.00"),
        ("cero contra celda vacía", "credito", "0", None),
        ("negativo con y sin decimales", "saldo_inicial", "-1000", "-1000.00"),
    )
    for etiqueta, campo, a, b in escrituras:
        caso(f"huella · ciega a {etiqueta}",
             R.huella_balance(dict(real, **{campo: a})),
             R.huella_balance(dict(real, **{campo: b})))

    ref = R.huella_balance(real)
    valores = (("un centavo en el saldo final", "saldo_final", "0.01"),
               ("un peso en el débito", "debito", "1"),
               ("un peso en el crédito", "credito", "1"),
               ("un peso en el saldo inicial", "saldo_inicial", "1"))
    for etiqueta, campo, delta in valores:
        g = dict(real, **{campo: D(str(real[campo] or 0)) + D(delta)})
        caso(f"huella · detecta {etiqueta}", True, R.huella_balance(g) != ref)


# =====================================================================
# COTEJO
# =====================================================================

def validar_cotejo(base: list[dict]) -> None:
    """Reemplazar un archivo: lo que cambió debe salir, y solo eso."""
    filas = numerar(copy.deepcopy(base))
    previas = {R.llave_balance(f): R.huella_balance(f) for f in filas}

    siguientes = copy.deepcopy(filas)
    modificada = siguientes[3]["codigo_puc"]
    siguientes[3]["debito"] = D(str(siguientes[3]["debito"])) + D("23000000")
    eliminada = siguientes.pop(7)["codigo_puc"]
    nueva = dict(siguientes[0], codigo_puc="9999", nombre_cuenta="Sembrada")
    siguientes.append(nueva)

    nuevas = {R.llave_balance(f): R.huella_balance(f) for f in siguientes}
    dif = R.cotejar(nuevas, previas)
    inv = {R.llave_balance(f): f["codigo_puc"] for f in filas + [nueva]}

    caso("cotejo · detecta la fila modificada",
         [modificada], [inv[k] for k in dif["modificadas"]])
    caso("cotejo · detecta la fila eliminada",
         [eliminada], [inv[k] for k in dif["eliminadas"]])
    caso("cotejo · detecta la fila nueva",
         ["9999"], [inv[k] for k in dif["nuevas"]])

    # NEGATIVO: el mismo archivo reescrito con otra escala no cambió nada
    reescrito = {}
    for f in copy.deepcopy(filas):
        for campo in ("saldo_inicial", "debito", "credito", "saldo_final"):
            f[campo] = f"{D(str(f[campo] or 0)):.4f}"
        reescrito[R.llave_balance(f)] = R.huella_balance(f)
    igual = R.cotejar(reescrito, previas)
    caso("cotejo · el mismo archivo con otra escala NO reporta cambios",
         (0, 0, 0),
         (len(igual["nuevas"]), len(igual["modificadas"]),
          len(igual["eliminadas"])))


# =====================================================================
# SELECCIÓN
# =====================================================================

def validar_motivos() -> None:
    """La cascada de selección define el ALCANCE del trabajo, así que se
    prueba con casos sembrados y no por inspección del código."""
    U, T, PV = D("1000"), D("50"), D("20")

    def m(sa, sc, usa_var=True):
        sa, sc = D(sa), D(sc)
        var = (sa - sc).quantize(CENT)
        pctv = ((sa - sc) / abs(sc) * 100).quantize(CENT) if sc else None
        return R.motivo_seleccion(sa, sc, var, pctv, U, T, PV, usa_var)

    caso("motivo · variación justo en el umbral marca Monto",
         "Monto", m("2000", "1000"))
    # Un centavo bajo el umbral, y con el porcentaje también por debajo: si
    # el comparativo fuera pequeño la misma variación entraría por
    # Comportamiento, que es correcto y es justo lo que este caso aísla.
    caso("motivo · un centavo bajo el umbral no marca Monto",
         None, m("100999.99", "100000.00"))
    caso("motivo · la misma variación con base pequeña entra por porcentaje",
         "Comportamiento", m("1999.99", "1000.00"))
    caso("motivo · saldo nuevo sobre el piso marca Cuenta nueva",
         "Cuenta nueva", m("500", "0"))
    caso("motivo · saldo nuevo bajo el piso no marca nada",
         None, m("49", "0"))
    caso("motivo · saldo que desaparece marca Cuenta cerrada",
         "Cuenta cerrada", m("0", "500"))
    caso("motivo · 20% sobre el piso marca Comportamiento",
         "Comportamiento", m("600", "500"))
    caso("motivo · 19% no marca Comportamiento", None, m("595", "500"))
    caso("motivo · con el criterio de porcentaje apagado, el 20% no marca",
         None, m("600", "500", usa_var=False))
    caso("motivo · saldo natural negativo marca Naturaleza",
         "Naturaleza", m("-500", "-450"))

    # La naturaleza se juzga contra el signo del CATÁLOGO, que en un archivo
    # que ya trae los signos aplicados no coincide con el saldo comparable.
    # Sin esta separación, todo pasivo de ese cliente saldría como excepción.
    caso("motivo · pasivo con saldo comparable negativo pero naturaleza "
         "correcta NO marca",
         None,
         R.motivo_seleccion(D("-500"), D("-450"), D("-50"), D("11.11"),
                            U, T, PV, True, naturaleza=D("500")))
    caso("motivo · naturaleza negativa marca aunque el comparable sea positivo",
         "Naturaleza",
         R.motivo_seleccion(D("500"), D("450"), D("50"), D("11.11"),
                            U, T, PV, True, naturaleza=D("-500")))
    caso("motivo · sin materialidad no se marca nada",
         None, R.motivo_seleccion(D("999999999999"), D(0), D("999999999999"),
                                  None, None, D(0), PV, True))
    # El orden de la cascada importa: una cuenta se marca por UN motivo, o los
    # conteos por motivo dejarían de sumar al total de seleccionadas.
    caso("motivo · Monto gana sobre Cuenta nueva cuando aplican los dos",
         "Monto", m("5000", "0"))


# =====================================================================
# CUADRE DEL ASIENTO
# =====================================================================

def validar_documentos() -> None:
    """Contra el archivo real de movimientos: es la única fuente
    independiente que tiene el papel."""
    mov = db.uno("""SELECT carga_id FROM core.encargo_insumo
                     WHERE tipo='MOV_ACTUAL'""")
    if not mov:
        resultados.append((False, "cuadre de documentos",
                           "no hay movimientos cargados"))
        return

    r = db.cuadre_documentos(str(mov["carga_id"]))
    informar("cuadre de documentos · archivo real",
             f"{r['documentos']} documentos · {r['descuadrados']} descuadrados "
             f"· {r['multi_fecha']} con más de una fecha "
             f"· {r['lineas_sin_documento']} líneas sin documento")
    caso("cuadre de documentos · num_doc identifica un asiento único",
         0, r["multi_fecha"],
         "si no es cero, el consecutivo se reutiliza y el control no concluye")
    caso("cuadre de documentos · todos los asientos cuadran",
         0, r["descuadrados"])


# =====================================================================
# DIRECCION DE LA VARIACION
# =====================================================================

def validar_direccion() -> None:
    """El mismo hecho economico debe leerse igual en cualquier cliente.

    Un pasivo que se paga -- 2505 SALARIOS POR PAGAR, de 140 a 8 millones --
    tiene que salir como DISMINUCION venga el archivo con la convencion del
    catalogo o con la del archivo. Sobre la cifra comparable no era asi: el
    signo dependia del ERP que exporto el archivo.
    """
    cat_ant, cat_act = D("140041409"), D("8069380")        # CATALOGO: pasivo +
    arc_ant, arc_act = D("-140041409"), D("-8069380")      # ARCHIVO:  pasivo -
    signo = -1

    # saldo_naturaleza = saldo_final * signo, en las dos convenciones
    nat_cat = ((cat_ant * 1), (cat_act * 1))               # ya viene en naturaleza
    nat_arc = ((arc_ant * signo), (arc_act * signo))
    caso("direccion · las dos convenciones dan la misma cifra en naturaleza",
         nat_cat, nat_arc)

    var = (nat_arc[1] - nat_arc[0]).quantize(CENT)
    caso("direccion · pagar un pasivo es una disminucion",
         True, var < 0, f"variacion en naturaleza: {var}")

    # y el alcance no se mueve: motivo_seleccion mide magnitudes
    umbral, trivial, pct = D("50000000"), D("1000000"), D("20")
    sobre_comparable = R.motivo_seleccion(
        arc_act, arc_ant, (arc_act - arc_ant), D("94.24"),
        umbral, trivial, pct, True, naturaleza=nat_arc[1])
    sobre_naturaleza = R.motivo_seleccion(
        nat_arc[1], nat_arc[0], var, D("-94.24"),
        umbral, trivial, pct, True, naturaleza=nat_arc[1])
    caso("direccion · cambiar la base no cambia el motivo",
         sobre_comparable, sobre_naturaleza)


# =====================================================================
# CODIGOS REPETIDOS
# =====================================================================

def validar_duplicados(base: list[dict]) -> None:
    """Sembrando la repeticion se comprueba que se resuelve segun su causa.

    Se siembra sobre el balance REAL para que el cuadre por nivel siga
    siendo el juez: si la consolidacion estuviera mal, el nivel dejaria de
    sumar cero y el caso 3 lo delataria.
    """
    def cifras(f):
        return tuple(Decimal(str(f[k] or 0)) for k in
                     ("saldo_inicial", "debito", "credito", "saldo_final"))

    # --- linea identica repetida: se conserva una
    origen = next(f for f in base if Decimal(str(f["saldo_final"] or 0)) != 0)
    sembrado = base + [dict(origen)]
    filas, dup = R.consolidar_duplicados(sembrado)
    caso("codigo repetido · linea identica no se duplica",
         len(base), len(filas))
    caso("codigo repetido · linea identica se declara",
         [(origen["codigo_puc"], "IDENTICA")],
         [(d["codigo_puc"], d["trato"]) for d in dup])
    caso("codigo repetido · linea identica conserva el saldo",
         cifras(origen),
         cifras(next(f for f in filas if f["codigo_puc"] == origen["codigo_puc"])))

    # --- cifras distintas bajo el mismo codigo: se suman
    partido = dict(origen)
    for k in ("saldo_inicial", "debito", "credito", "saldo_final"):
        partido[k] = Decimal(str(origen[k] or 0)) / 2
    filas, dup = R.consolidar_duplicados(base + [partido])
    consolidada = next(f for f in filas if f["codigo_puc"] == origen["codigo_puc"])
    caso("codigo repetido · cifras distintas se suman",
         "SUMADA", dup[0]["trato"] if dup else "sin declarar")
    caso("codigo repetido · la suma es la de las partes",
         tuple(v + v / 2 for v in cifras(origen)), cifras(consolidada))

    # --- el nivel sigue siendo el juez
    niveles = db.niveles_cargables()
    antes = {q["nivel"]: q["estado"] for q in R.cuadre_por_nivel(base, niveles)}
    filas, _ = R.consolidar_duplicados(base + [dict(origen)])
    despues = {q["nivel"]: q["estado"] for q in R.cuadre_por_nivel(filas, niveles)}
    caso("codigo repetido · deduplicar no altera el cuadre por nivel",
         antes, despues,
         "si cambia, la consolidacion movio un saldo que no debia mover")


# =====================================================================

def main() -> int:
    base = numerar(base_real())
    if len(base) < 20:
        print("No hay un balance actual promovido con suficientes filas.")
        print("Cargue y promueva el balance del corte antes de validar.")
        return 1

    print(f"Base: {len(base)} filas del balance actual real.\n")
    validar_cuadre_linea(base)
    validar_cuadre_nivel(base)
    validar_huellas(base)
    validar_cotejo(base)
    validar_motivos()
    validar_direccion()
    validar_duplicados(base)
    validar_documentos()

    fallan = [r for r in resultados if not r[0]]
    for ok, nombre, nota in resultados:
        print(f"  {'PASA ' if ok else 'FALLA'}  {nombre}"
              + (f"\n            {nota}" if nota else ""))
    print(f"\n{len(resultados) - len(fallan)} de {len(resultados)} casos pasan.")
    if fallan:
        print("\nEl motor NO está validado. Casos que fallan:")
        for _, nombre, nota in fallan:
            print(f"  · {nombre}: {nota}")
    return 1 if fallan else 0


if __name__ == "__main__":
    db.abrir()
    try:
        sys.exit(main())
    finally:
        db.cerrar()
