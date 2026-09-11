"""
La conclusión del papel de trabajo, contada en primera persona.

Vive aparte de papel.py porque es lo único del papel que se lee como prosa
y no como tabla, y porque es la pieza que alguien firma. Merece un archivo.

Regla que ordena el módulo, y es la misma de todo el sistema: **cada frase
sale de un dato del papel**. Los periodos vienen del encargo, las huellas del
contrato de datos, el umbral de la materialidad de la fase, el resultado de
cada control del propio control. No hay nada redactado a mano ni generado por
un modelo.

Eso no es purismo: es lo que hace imposible que el relato y las cifras se
contradigan. Si el texto dice que ejecuté cuatro controles, es porque la
lista tiene cuatro. Una conclusión escrita a mano se desactualiza el día que
alguien cambia un umbral y nadie se acuerda de reescribirla, y entonces el
papel afirma una cosa y sus tablas otra.

Va en primera persona porque un papel de trabajo lo firma una persona y
declara lo que ESA persona hizo. «Se ejecutaron los controles» no dice quién
responde; «ejecuté los controles» sí.
"""
from __future__ import annotations

import analisis as A

MOTIVO_EXPLICADO = {
    "Monto": "su variación superó la materialidad",
    "Cuenta nueva": "nacieron en el periodo, sin saldo comparativo",
    "Cuenta cerrada": "quedaron en cero habiendo tenido saldo antes",
    "Comportamiento": "se movieron por encima del porcentaje fijado aunque no "
                      "alcanzaran la materialidad en pesos",
    "Naturaleza": "quedaron con el saldo del lado contrario al de su naturaleza",
}

ESTADO_CONTROL = {
    "OK": "pasó",
    "FALLA": "FALLÓ",
    "BLOQUEANTE": "FALLÓ",
    "ALERTA": "quedó en alerta",
    "NO_EJECUTADO": "no se pudo ejecutar",
}


def _miles(n: int) -> str:
    """Separador de miles a la colombiana."""
    return f"{n:,}".replace(",", ".")


def _fecha(v) -> str:
    """dd/mm/aaaa. Un papel de trabajo colombiano no lleva fechas en ISO."""
    if hasattr(v, "strftime"):
        return v.strftime("%d/%m/%Y")
    t = str(v)[:10]
    return f"{t[8:10]}/{t[5:7]}/{t[0:4]}" if len(t) == 10 else t


def _plural(n: int, singular: str, plural: str) -> str:
    """Concordancia. "1 cuenta(s)" y "1 puntos" delatan una plantilla, y en un
    documento que alguien firma eso resta credibilidad a todo lo demas."""
    return f"{n} {singular if abs(n) == 1 else plural}"


def _fase(d: dict) -> str:
    """El nombre legible de la fase. El codigo -- PLANEACION -- sirve para la
    base de datos, no para un parrafo."""
    nombre = ((d.get("materialidad") or {}).get("nombre") or "").strip()
    return nombre.lower() if nombre else str(d.get("fase", "")).lower()


# =====================================================================
# EL RELATO DEL PROCEDIMIENTO
# =====================================================================

def _que_compare(enc: dict, d: dict) -> str:
    return (
        f"Ejecuté una revisión analítica de las variaciones de "
        f"{enc['razon_social']} con corte al {_fecha(enc['fecha_corte'])}, en la fase "
        f"de {_fase(d)}. Comparé cada cuenta contra el periodo "
        f"que le corresponde según su clase: las clases 1 a 3 contra el cierre "
        f"del {_fecha(enc['fecha_cierre_anterior'])}, porque arrastran saldo de un año "
        f"al otro; y las clases 4 a 7 contra el mismo corte del año anterior, "
        f"el {_fecha(enc['fecha_corte_anterior'])}, porque arrancan cada año en cero y "
        f"compararlas contra diciembre mediría un ejercicio completo contra "
        f"medio ejercicio.")


def _sobre_que_datos(contrato: list[dict]) -> str:
    cargados = [c for c in contrato if c.get("cargado")]
    balances = [c for c in cargados if c["tipo"].startswith("BAL")]
    filas = sum(c.get("filas_promovidas") or 0 for c in balances)
    faltantes = [c["insumo"] for c in contrato
                 if c.get("requerido") and not c.get("cargado")]

    uno = len(cargados) == 1
    texto = (
        f"Trabajé sobre "
        + ("un archivo entregado por el cliente, del cual"
           if uno else
           f"{len(cargados)} archivos entregados por el cliente, de los cuales")
        + f" los balances aportaron {_miles(filas)} filas validadas e "
        f"incorporadas. La huella SHA-256 de cada archivo queda registrada en "
        f"el contrato de datos, junto con la columna de la que salió cada "
        f"cifra: si el cliente reemplaza un archivo, la huella cambia y este "
        f"papel deja de corresponder a lo que revisé.")
    if faltantes:
        texto += (f" Quedaron sin cargar insumos requeridos: "
                  f"{', '.join(faltantes)}.")
    return texto


def _como_defini_el_alcance(d: dict) -> list[str]:
    if not d.get("aplica"):
        return []

    criterios = [f"una variación en pesos igual o mayor a la materialidad de "
                 f"la fase, {A._cop(d['umbral'])}"]
    if d.get("aplica_variacion", True):
        criterios.append(f"una variación porcentual desde el "
                         f"{d['pct_variacion']}%")
    else:
        criterios.append("el criterio de variación porcentual desactivado por "
                         "decisión del encargo")
    if d.get("aplica_trivialidad", True):
        criterios.append(f"un error trivial del {d['pct_trivialidad']}% de la "
                         f"materialidad, {A._cop(d['trivialidad'])}, para no "
                         f"marcar cuentas por cifras irrelevantes")
    else:
        criterios.append("sin error trivial, de modo que cualquier variación "
                         "que cruce el porcentaje se reporta por pequeña que sea")
    criterios.append("y los criterios estructurales de cuenta nueva, cuenta "
                     "cerrada y naturaleza invertida")

    parrafos = [
        f"Definí el alcance con {'; '.join(criterios)}. De las "
        f"{d['total_cuentas']} cuentas comparadas a nivel de cuenta (cuatro "
        f"dígitos), seleccioné {d['significativas']} para revisión."]

    motivos = [(m, n) for m, n in (d.get("por_motivo") or {}).items() if n]
    if motivos:
        partes = [f"{n} porque {MOTIVO_EXPLICADO.get(m, m.lower())}"
                  for m, n in motivos]
        parrafos.append(
            "El desglose de por qué entró cada una: " + "; ".join(partes)
            + ". Cada cuenta se marca por un solo motivo, el primero que aplica "
            "en orden de fuerza, de modo que estas cifras suman las "
            "seleccionadas sin contar ninguna dos veces.")
    return parrafos


def _que_controles(previos: list[dict], gates: list[dict]) -> str:
    lineas = []
    for c in previos + gates:
        if c["codigo"] == "G04":
            continue                 # se explica aparte, por lo que es
        estado = ESTADO_CONTROL.get(c["estado"], c["estado"])
        lineas.append(f"{c['codigo']} ({c['nombre']}) {estado}")

    hay_independiente = any(g["codigo"] == "G03" and g["es_evidencia"]
                            for g in gates)
    texto = (f"Corrí {_plural(len(lineas), 'control', 'controles')} antes de concluir: "
             + "; ".join(lineas) + ".")
    if hay_independiente:
        texto += (" De todos ellos, el cruce contra el archivo de movimientos "
                  "es el único que contrasta las cifras contra una fuente "
                  "distinta del balance; los demás verifican el balance contra "
                  "sí mismo, y por construcción no podrían detectar un balance "
                  "internamente coherente pero equivocado.")
    texto += (" Incluí además un control de consistencia de la selección (G04) "
              "que cuadra por construcción, y por eso lo declaré expresamente "
              "como NO constitutivo de evidencia: presentar un cuadre "
              "tautológico como prueba es peor que no presentarlo, porque nadie "
              "lo vuelve a mirar.")
    return texto


def _tolerancias(gates: list[dict]) -> list[str]:
    g3 = next((g for g in gates if g["codigo"] == "G03"), None)
    cifras = (g3 or {}).get("cifras") or {}
    redondeos = cifras.get("por_redondeo") or []
    if not redondeos:
        return []

    detalle = ", ".join(f"{r['cuenta']} por {r['diferencia']}"
                        for r in redondeos)
    una = len(redondeos) == 1
    return [
        f"En el cruce contra movimientos admití hasta "
        f"{cifras.get('tolerancia_por_cuenta')} de diferencia por cuenta, que "
        f"es cuanto puede variar el redondeo entre dos exportes del mismo "
        f"mayor. "
        + (f"Una cuenta se apoyó en esa tolerancia y la dejo listada"
           if una else
           f"{len(redondeos)} cuentas se apoyaron en esa tolerancia y las dejo "
           f"listadas")
        + f" con su diferencia: {detalle}. Lo declaro porque una tolerancia "
          f"que se aplica en silencio equivale a no haber corrido el control."]


def _que_deje_por_fuera(d: dict) -> list[str]:
    if not d.get("aplica"):
        return []

    n = d["total_cuentas"] - d["significativas"]
    monto = A._cop(d.get("residuo_no_seleccionado"))
    sujeto = ("La cuenta que no seleccioné suma" if n == 1
              else f"Las {n} cuentas que no seleccioné suman")
    base = f"{sujeto} {monto} en variaciones absolutas, "

    if d.get("residuo_supera_umbral"):
        return [base + (
            "por ENCIMA de la materialidad de la fase. Ese conjunto podría "
            "contener un error material por acumulación aunque ninguna cuenta "
            "lo alcance por separado, de modo que el alcance debe ampliarse o "
            "dejarse constancia razonada de por qué se acepta ese residuo.")]
    return [base + ("por debajo de la materialidad de la fase. Ni "
                    "individualmente ni sumadas alcanzan a ser materiales.")]


def relato(enc: dict, contrato: list[dict], previos: list[dict],
           gates: list[dict], d: dict) -> list[str]:
    """El procedimiento completo, párrafo por párrafo."""
    return ([_que_compare(enc, d), _sobre_que_datos(contrato)]
            + _como_defini_el_alcance(d)
            + [_que_controles(previos, gates)]
            + _tolerancias(gates)
            + _que_deje_por_fuera(d))


# =====================================================================
# LA CONCLUSIÓN
# =====================================================================

def armar(enc: dict, contrato: list[dict], gates: list[dict],
          previos: list[dict], riesgo: dict, d: dict) -> dict:
    """Estado y texto de la conclusión.

    Tres reglas, en este orden:

    1. Si un control que CONSTITUYE EVIDENCIA falló, o un control previo
       quedó bloqueante, no se concluye razonabilidad. Se dice que no se
       puede concluir, que es una conclusión legítima y mucho más útil que
       una favorable sobre datos que el propio papel marcó como no aptos.
    2. Sin materialidad aplicada no hay alcance, y sin alcance no hay nada
       que concluir.
    3. Si todo pasó pero algo no pudo ejecutarse, o el residuo no
       seleccionado supera la materialidad, se concluye con salvedades
       explícitas.

    G04 no entra en la decisión: cuadra por construcción y está declarado
    como no evidencia.
    """
    evidencia = [g for g in gates if g["es_evidencia"]]
    bloqueados = [c for c in previos if c["estado"] == "BLOQUEANTE"]
    fallas = [g for g in evidencia if g["estado"] == "FALLA"] + bloqueados
    sin_correr = [g for g in evidencia if g["estado"] == "NO_EJECUTADO"]
    alertas = [c for c in previos if c["estado"] == "ALERTA"]

    parrafos = relato(enc, contrato, previos, gates, d)

    if fallas:
        estado = "NO_CONCLUYENTE"
        cierre = (
            "No me es posible concluir sobre la razonabilidad de las "
            "variaciones. "
            + "; ".join(f"{g['nombre']} falló" for g in fallas)
            + ". Mientras el origen de esas diferencias no se resuelva, todo lo "
              "demás de este papel se apoya en cifras que no se sostienen, y "
              "firmar una conclusión favorable sería dar por verificado "
              "precisamente lo que este mismo papel señala como no verificable.")
    elif not d.get("aplica"):
        estado = "NO_CONCLUYENTE"
        cierre = (
            "No me es posible concluir. La fase no tiene materialidad "
            "aplicada, de modo que ninguna cuenta quedó seleccionada: el "
            "comparativo está calculado, pero sin umbral no hay alcance "
            "definido, y sin alcance no hay conclusión que sostener.")
    else:
        salvedades = []
        if sin_correr:
            salvedades.append(
                "no pude ejecutar "
                + " ni ".join(str(g["nombre"]) for g in sin_correr)
                + ", de modo que las cifras quedan verificadas contra sí mismas "
                  "y no contra una fuente independiente")
        if d.get("residuo_supera_umbral"):
            salvedades.append(
                "el conjunto de variaciones que no seleccioné supera la "
                "materialidad de la fase")
        if alertas:
            salvedades.append(
                "quedaron en alerta " + " y ".join(
                    f"{c['codigo']} ({c['nombre']})"
                    for c in alertas))

        if salvedades:
            estado = "RAZONABLE_CON_SALVEDADES"
            cierre = (
                "Concluyo que las variaciones del periodo son razonables en su "
                "origen y magnitud, CON LAS SIGUIENTES SALVEDADES: "
                + "; ".join(salvedades)
                + ". La conclusión se sostiene únicamente en la medida en que "
                  "esas salvedades se atiendan, o en que se documente por qué "
                  "se aceptan.")
        else:
            estado = "RAZONABLE"
            cierre = (
                "Concluyo que las variaciones del periodo son razonables. Los "
                "controles que constituyen evidencia se ejecutaron sin "
                "excepciones, las cuentas que seleccioné quedaron cruzadas "
                "contra el archivo de movimientos —una fuente independiente del "
                "balance— y lo que dejé por fuera no alcanza a ser material ni "
                "individualmente ni sumado.")

    # El límite del papel se declara siempre, gane o pierda la conclusión: es
    # lo que evita que alguien lea esto como una opinión sobre los estados
    # financieros, que es otra cosa y exige otros procedimientos.
    cierre += (" Esta conclusión se circunscribe a la razonabilidad de las "
               "VARIACIONES frente a los periodos comparativos, en el marco de "
               "un procedimiento analítico (NIA 520). No constituye opinión "
               "sobre los estados financieros en su conjunto, ni reemplaza las "
               "pruebas sustantivas sobre los saldos de las cuentas "
               "seleccionadas.")

    parrafos.append(cierre)
    parrafos.append(
        f"El índice de riesgo de este papel quedó en {riesgo['nivel']} con "
        f"{_plural(riesgo['puntos'], 'punto', 'puntos')}; cada punto declara su origen en la sección "
        f"de riesgo. Responsable del procedimiento: "
        f"{enc.get('responsable') or 'sin asignar'}.")

    return {"estado": estado,
            "texto": " ".join(parrafos),
            "parrafos": parrafos,
            "cierre": cierre,
            "riesgo": riesgo["nivel"],
            "controles_evidencia": len(evidencia),
            "controles_fallidos": len(fallas),
            "controles_no_ejecutados": len(sin_correr)}
