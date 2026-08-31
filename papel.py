"""
Papel de trabajo: revisión analítica de variaciones (NIA 520).

Ensambla, a partir de lo que ya existe en la base, el entregable formal:
de qué archivo salió cada cifra, qué controles se corrieron y contra qué,
qué se seleccionó y por qué, qué quedó sin explicar, y una conclusión.

Regla que ordena todo el módulo: **aquí no se calcula nada nuevo**. Las
cifras salen de analisis.py y de consultas a core.balance; este archivo
las organiza, las contrasta contra los controles y declara el resultado.
La IA, si se usa, entra al final y solo redacta.

Distinción que la norma exige y que se respeta explícitamente: un control
solo es EVIDENCIA si puede fallar y si contrasta contra algo que no se
derive de lo que está verificando. Los controles que cuadran por
construcción se incluyen -- son útiles como consistencia interna -- pero
van marcados `es_evidencia: False`. Un papel que presenta un cuadre
tautológico como prueba es peor que uno que falla, porque nadie lo
vuelve a mirar.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import analisis as A
import db

VERSION = "1.0"

# ---------------------------------------------------------------- marcas
# Una marca sin leyenda es un símbolo, no evidencia (NIA 230): cada una
# declara qué procedimiento se ejecutó y contra qué se contrastó, de modo
# que un tercero pueda reconstruirlo sin hablar con quien lo hizo.
MARCAS = [
    {"marca": "✓", "nombre": "Cuadre por nivel", "nia": "NIA 500",
     "procedimiento": "Suma de los saldos de todas las cuentas de un nivel completo.",
     "contra": "La ecuación contable: un nivel completo del balance suma cero por sí solo.",
     "evidencia": True},
    {"marca": "Σ", "nombre": "Cuadre por línea", "nia": "NIA 500",
     "procedimiento": "Saldo inicial + débitos − créditos, cuenta por cuenta.",
     "contra": "El saldo final que declara el propio balance en esa misma fila.",
     "evidencia": True},
    {"marca": "M", "nombre": "Cruce con movimientos", "nia": "NIA 500",
     "procedimiento": "Suma de los movimientos del periodo de la cuenta y sus auxiliares.",
     "contra": "El archivo de movimientos, que es una fuente DISTINTA del balance. "
               "Es el único control aquí que contrasta contra un origen independiente.",
     "tolerancia": "Hasta un peso de diferencia por cuenta, para absorber el "
                   "redondeo entre dos exportes del mismo mayor. Las cuentas que "
                   "usan esa tolerancia se listan con su diferencia.",
     "evidencia": True},
    {"marca": "Δ", "nombre": "Comparativo", "nia": "NIA 520",
     "procedimiento": "Saldo del corte menos saldo del periodo comparativo, en saldo natural.",
     "contra": "El balance del periodo que corresponde a la clase: cierre anterior "
               "para clases 1 a 3, mismo corte del año anterior para 4 a 7.",
     "evidencia": True},
    {"marca": "=", "nombre": "Consistencia de la selección", "nia": "—",
     "procedimiento": "Seleccionadas + no seleccionadas contra el total de cuentas.",
     "contra": "Sí mismo: las dos partes salen de partir el total. "
               "Cuadra por construcción y NO constituye evidencia.",
     "evidencia": False},
    {"marca": "?", "nombre": "No verificado", "nia": "—",
     "procedimiento": "El control no pudo ejecutarse por falta del insumo.",
     "contra": "Nada. Se declara para no dar por pasado un control que ni corrió.",
     "evidencia": False},
]


# ================================================================ helpers

def _control(codigo, marca, nombre, estado, detalle, evidencia=True, cifras=None):
    return {"codigo": codigo, "marca": marca, "nombre": nombre,
            "estado": estado, "detalle": detalle,
            "es_evidencia": evidencia, "cifras": cifras or {}}


def _cuadre_niveles(carga_id: str) -> list[dict]:
    """Recalculado desde core.balance, no leído de un resultado guardado:
    el papel debe poder reproducir el control, no repetir lo que alguien
    anotó cuando se cargó el archivo."""
    if not carga_id:
        return []
    return db.varios(
        """SELECT b.nivel, count(*) AS filas,
                  sum(b.saldo_final) AS suma,
                  n.nivel_completo, n.orden
           FROM core.balance b
           JOIN core.nivel_cargable n ON n.nivel = b.nivel
           WHERE b.carga_id = %s
           GROUP BY b.nivel, n.nivel_completo, n.orden
           ORDER BY n.orden""",
        (carga_id,),
    )


def _descuadres_linea(carga_id: str) -> list[dict]:
    if not carga_id:
        return []
    return db.varios(
        """SELECT codigo_puc, nombre_cuenta,
                  (saldo_inicial + debito - credito - saldo_final) AS diferencia
           FROM core.balance
           WHERE carga_id = %s
             AND (saldo_inicial + debito - credito) <> saldo_final
           ORDER BY abs(saldo_inicial + debito - credito - saldo_final) DESC
           LIMIT 100""",
        (carga_id,),
    )


def _cuentas_fuera_de_catalogo(carga_id: str) -> list[dict]:
    """Cuentas del cliente que no existen en el catálogo PUC. No es un
    error -- el cliente puede tener auxiliares propios -- pero sí algo que
    el papel debe declarar en vez de callar."""
    if not carga_id:
        return []
    return db.varios(
        """SELECT b.codigo_puc, b.nombre_cuenta
           FROM core.balance b
           LEFT JOIN core.puc p ON p.codigo = b.codigo_puc
           WHERE b.carga_id = %s AND b.nivel = 'Cuenta' AND p.codigo IS NULL
           ORDER BY b.codigo_puc""",
        (carga_id,),
    )


# ====================================================== contrato de datos

def _contrato_datos(encargo_id: str) -> list[dict]:
    """De qué archivo y de qué columna salió cada cifra. Sin esto el papel
    no es reproducible: es lo que permite que otro repita el trabajo."""
    filas = []
    for i in db.checklist(encargo_id):
        if not i["carga_id"]:
            filas.append({
                "insumo": i["insumo"], "tipo": i["tipo"],
                "requerido": i["requerido"], "cargado": False,
            })
            continue

        c = db.carga(i["carga_id"])
        perfil = db.uno("SELECT mapeo, version FROM core.perfil_mapeo WHERE id=%s",
                        (c["perfil_id"],)) if c["perfil_id"] else None
        mapeo = (perfil or {}).get("mapeo") or {}

        filas.append({
            "insumo": i["insumo"], "tipo": i["tipo"],
            "requerido": i["requerido"], "cargado": True,
            "carga_id": i["carga_id"],
            "archivo": (c["archivo"] or "").replace("\\", "/").rsplit("/", 1)[-1],
            # La huella es lo que ata el papel a un archivo concreto: si el
            # cliente reenvía otro, el hash cambia y el papel deja de
            # corresponder a lo que se revisó.
            "huella_sha256": c["hash_sha256"],
            "hoja": mapeo.get("hoja"),
            "formato_fecha": mapeo.get("formato_fecha"),
            "columnas": mapeo.get("columnas") or {},
            "perfil_version": (perfil or {}).get("version"),
            "periodo": {"inicio": c["periodo_ini"], "fin": c["periodo_fin"]},
            "filas_leidas": c["filas_staging"],
            # Cargado no es lo mismo que promovido: una carga puede quedarse
            # en staging y nunca llegar a core.balance. Se cuenta contra la
            # tabla en vez de leer `filas_cargadas`, que es lo que alguien
            # anotó al promover -- y aquí hace falta saber qué hay, no qué
            # se dijo que había.
            "filas_promovidas": (
                db.uno("SELECT count(*) AS n FROM core.balance WHERE carga_id=%s",
                       (i["carga_id"],))["n"]
                if i["tipo"].startswith("BAL") else c["filas_cargadas"]),
            "estado": c["estado"],
            "subido_por": c["subido_por"],
            "fecha_carga": c["fecha_carga"],
        })
    return filas


# ================================================ controles antes de cruzar

def _controles_previos(enc: dict, contrato: list[dict]) -> list[dict]:
    """Integridad ANTES de comparar. Cruzar dos balances de clientes,
    periodos o monedas distintas produce un número perfectamente formado
    y completamente falso."""
    ctrl = []
    por_tipo = {c["tipo"]: c for c in contrato if c.get("cargado")}

    # -- misma entidad
    faltan = [c["insumo"] for c in contrato
              if c["requerido"] and not c.get("cargado")]
    # Un balance cargado pero sin promover tiene cero filas en core.balance:
    # el análisis lo leería como saldos en cero y el comparativo saldría
    # coherente y falso. Tener el archivo no es tenerlo cargado.
    vacios = [c["insumo"] for c in contrato
              if c.get("cargado") and c.get("filas_promovidas") == 0]
    if faltan:
        detalle = (f"Faltan: {', '.join(faltan)}. Sin ellos el comparativo "
                   "no se puede armar.")
    elif vacios:
        detalle = (f"{', '.join(vacios)}: el archivo está cargado pero ninguna "
                   "de sus filas llegó al balance. Quedó en staging sin "
                   "promover, así que sus saldos entrarían al comparativo "
                   "como cero.")
    else:
        detalle = "Todos los insumos requeridos están cargados y promovidos."
    ctrl.append(_control(
        "P01", "✓", "Insumos requeridos completos",
        "OK" if not (faltan or vacios) else "BLOQUEANTE", detalle,
        cifras={"faltan": faltan, "sin_promover": vacios} if (faltan or vacios) else None,
    ))

    # -- periodos: que cada balance sea del periodo que dice ser
    esperado = {
        "BAL_ACTUAL": enc["fecha_corte"],
        "BAL_CIERRE_ANTERIOR": enc["fecha_cierre_anterior"],
        "BAL_CORTE_ANTERIOR": enc["fecha_corte_anterior"],
    }
    desfases = []
    for tipo, fin in esperado.items():
        c = por_tipo.get(tipo)
        if not c:
            continue
        real = c["periodo"]["fin"]
        if real and fin and real != fin:
            desfases.append(f"{c['insumo']}: se esperaba {fin} y el archivo declara {real}")
    ctrl.append(_control(
        "P02", "✓", "Periodos de los comparativos",
        "OK" if not desfases else "ALERTA",
        "Cada balance corresponde al periodo que le asigna la regla de comparación."
        if not desfases else " · ".join(desfases),
    ))

    # -- moneda: NO se asume
    ctrl.append(_control(
        "P03", "?", "Moneda declarada", "ALERTA",
        "Ningún insumo declara la moneda y el sistema no la registra. Las cifras "
        "se presentan sin unidad monetaria verificada; se asume que las tres "
        "fuentes están en la misma moneda porque provienen del mismo ERP, "
        "pero eso NO está comprobado. Si alguna estuviera reexpresada, el "
        "comparativo sería inválido y este papel no lo detectaría.",
        evidencia=False,
    ))

    # -- catálogo
    fuera = _cuentas_fuera_de_catalogo(por_tipo.get("BAL_ACTUAL", {}).get("carga_id"))
    ctrl.append(_control(
        "P04", "✓", "Cuentas contra el catálogo PUC",
        "OK" if not fuera else "ALERTA",
        "Todas las cuentas del corte existen en el catálogo." if not fuera
        else f"{len(fuera)} cuentas no están en el catálogo Decreto 2650. "
             "Puede ser normal (el cliente usa cuentas propias) pero su naturaleza "
             "se resolvió heredando de la clase, no de una declaración explícita.",
        cifras={"cuentas": [f["codigo_puc"] for f in fuera[:20]]},
    ))
    return ctrl


# =========================================================== gates / cuadres

def _gates(encargo_id: str, d: dict) -> list[dict]:
    """Controles sobre las cifras. El orden va de más fuerte a más débil,
    y cada uno declara si constituye evidencia."""
    gates = []
    cargas = {i["tipo"]: i["carga_id"] for i in db.checklist(encargo_id)}

    # -- G01 cuadre por nivel, en los tres balances
    detalle_niveles = {}
    falla_nivel = []
    for tipo in ("BAL_ACTUAL", "BAL_CIERRE_ANTERIOR", "BAL_CORTE_ANTERIOR"):
        niveles = _cuadre_niveles(cargas.get(tipo))
        detalle_niveles[tipo] = [
            {"nivel": n["nivel"], "filas": n["filas"],
             "suma": A._cop(n["suma"]), "completo": n["nivel_completo"],
             "estado": ("n/a" if not n["nivel_completo"]
                        else "OK" if Decimal(n["suma"]).quantize(Decimal("0.01")) == 0
                        else "DESCUADRE")}
            for n in niveles
        ]
        falla_nivel += [f"{tipo}/{n['nivel']}" for n in detalle_niveles[tipo]
                        if n["estado"] == "DESCUADRE"]
    gates.append(_control(
        "G01", "✓", "Cuadre por nivel",
        "OK" if detalle_niveles and not falla_nivel
        else "NO_EJECUTADO" if not any(detalle_niveles.values()) else "FALLA",
        "Cada nivel completo suma cero: la ecuación contable se sostiene en los "
        "tres balances." if not falla_nivel
        else f"No suman cero: {', '.join(falla_nivel)}. El balance está incompleto "
             "o contaminado; nada de lo que sigue es confiable.",
        cifras=detalle_niveles,
    ))

    # -- G02 cuadre por línea
    malas = {t: _descuadres_linea(cargas.get(t))
             for t in ("BAL_ACTUAL", "BAL_CIERRE_ANTERIOR", "BAL_CORTE_ANTERIOR")}
    total_malas = sum(len(v) for v in malas.values())
    gates.append(_control(
        "G02", "Σ", "Cuadre por línea",
        "OK" if total_malas == 0 else "FALLA",
        "En cada cuenta, saldo inicial más débitos menos créditos reproduce el "
        "saldo final declarado." if total_malas == 0
        else f"{total_malas} cuentas donde el saldo final no se explica con sus "
             "propios movimientos del periodo.",
        cifras={t: [{"codigo": m["codigo_puc"], "nombre": m["nombre_cuenta"],
                     "diferencia": A._cop(m["diferencia"])} for m in v[:20]]
                for t, v in malas.items() if v},
    ))

    # -- G03 cruce contra movimientos: el ANCLA independiente
    if not cargas.get("MOV_ACTUAL"):
        gates.append(_control(
            "G03", "?", "Cruce con movimientos (fuente independiente)",
            "NO_EJECUTADO",
            "No hay movimientos cargados. El único control que contrasta el balance "
            "contra una fuente distinta NO pudo ejecutarse: las cifras solo están "
            "verificadas contra sí mismas.",
        ))
    else:
        revisadas, cuadran, no_cuadran, redondeos = 0, 0, [], []
        tolerancia = A._cop(A.TOLERANCIA_CUADRE)
        for f in d["filas"]:
            if not f["significativa"]:
                continue
            ev = A.evidencia_cuenta(encargo_id, d["fase"], f["cuenta"])
            c = ev.get("cuadre") if ev.get("listo") else None
            if not c:
                continue
            revisadas += 1
            fila = {"cuenta": f["cuenta"], "nombre": f["nombre"],
                    "contra": c["contra"], "esperado": c["esperado"],
                    "neto_movimientos": c["neto"],
                    "diferencia": c["diferencia"]}
            if c["cuadra"]:
                cuadran += 1
                # Cuadra dentro de la tolerancia pero no exacto: se declara.
                # Una tolerancia que se aplica en silencio es lo mismo que no
                # haber corrido el control.
                if c.get("por_redondeo"):
                    redondeos.append(fila)
            else:
                no_cuadran.append(fila)
        gates.append(_control(
            "G03", "M", "Cruce con movimientos (fuente independiente)",
            "NO_EJECUTADO" if revisadas == 0 else "OK" if not no_cuadran else "FALLA",
            (f"En {cuadran} de {revisadas} cuentas seleccionadas, la suma de los "
             "movimientos del periodo reproduce la cifra del balance. Es el único "
             f"control contra un origen distinto. Se admite hasta {tolerancia} "
             "de diferencia por cuenta, que es lo que puede variar el redondeo "
             "entre dos exportes del mismo mayor."
             + (f" {len(redondeos)} cuenta(s) cuadran dentro de esa tolerancia "
                "sin ser exactas y se detallan abajo." if redondeos else ""))
            if revisadas else
            "Ninguna cuenta seleccionada tiene movimientos asociados.",
            cifras={"revisadas": revisadas, "cuadran": cuadran,
                    "tolerancia_por_cuenta": tolerancia,
                    "por_redondeo": redondeos,
                    "no_cuadran": no_cuadran},
        ))

    # -- G04 consistencia de la selección: TAUTOLÓGICO, declarado
    sel = d["significativas"]
    total = d["total_cuentas"]
    gates.append(_control(
        "G04", "=", "Consistencia de la selección",
        "OK" if sel + (total - sel) == total else "FALLA",
        f"{sel} cuentas seleccionadas más {total - sel} no seleccionadas suman las "
        f"{total} comparadas. Cuadra por construcción: las dos partes salen de "
        "partir el mismo total. Se incluye como control interno, NO como evidencia.",
        evidencia=False,
        cifras={"seleccionadas": sel, "no_seleccionadas": total - sel, "total": total},
    ))
    return gates


# ================================================================= riesgo

def _riesgo(gates: list[dict], previos: list[dict], d: dict) -> dict:
    """Índice con la fuente de cada punto. No generaliza: un descuadre no
    pesa lo mismo que una moneda sin declarar."""
    puntos = []

    def sumar(n, motivo, origen):
        puntos.append({"puntos": n, "motivo": motivo, "origen": origen})

    por_codigo = {g["codigo"]: g for g in gates + previos}

    if por_codigo.get("G01", {}).get("estado") == "FALLA":
        sumar(5, "Un nivel del balance no suma cero", "Control G01")
    if por_codigo.get("G02", {}).get("estado") == "FALLA":
        sumar(4, "Hay cuentas cuyo saldo final no se explica con sus movimientos",
              "Control G02")
    g3 = por_codigo.get("G03", {})
    if g3.get("estado") == "FALLA":
        sumar(4, "Los movimientos no reproducen la cifra en alguna cuenta seleccionada",
              "Control G03")
    elif g3.get("estado") == "NO_EJECUTADO":
        sumar(3, "El único control contra una fuente independiente no se pudo correr",
              "Control G03")
    if por_codigo.get("P02", {}).get("estado") == "ALERTA":
        sumar(3, "Algún comparativo no corresponde al periodo esperado", "Control P02")
    if por_codigo.get("P03", {}).get("estado") == "ALERTA":
        sumar(2, "La moneda no está declarada en ninguna fuente", "Control P03")
    if por_codigo.get("P04", {}).get("estado") == "ALERTA":
        sumar(1, "Hay cuentas fuera del catálogo, con naturaleza heredada", "Control P04")
    if d.get("residuo_supera_umbral"):
        sumar(3, "Lo no seleccionado supera la materialidad de la fase",
              "Control de alcance")
    if not d.get("aplica"):
        sumar(4, "No hay materialidad aplicada: ninguna cuenta quedó seleccionada",
              "Parámetros del encargo")

    total = sum(p["puntos"] for p in puntos)
    nivel = ("BAJO" if total <= 2 else "MEDIO" if total <= 5
             else "ALTO" if total <= 9 else "MÁXIMO")
    return {"puntos": total, "nivel": nivel, "detalle": puntos}


# ============================================================== conclusión

def _conclusion(gates: list[dict], riesgo: dict, d: dict) -> dict:
    """Se arma con los resultados, no se redacta a mano. Si un control que
    constituye evidencia falló, no se concluye razonabilidad: se dice que
    no se puede concluir."""
    evidencia = [g for g in gates if g["es_evidencia"]]
    fallas = [g for g in evidencia if g["estado"] == "FALLA"]
    sin_correr = [g for g in evidencia if g["estado"] == "NO_EJECUTADO"]

    if fallas:
        estado, texto = "NO_CONCLUYENTE", (
            "No es posible concluir sobre la razonabilidad de las variaciones: "
            + "; ".join(f"{g['nombre']} falló" for g in fallas)
            + ". Antes de continuar debe resolverse el origen de esos descuadres, "
              "porque el resto del análisis se apoya en cifras que no se sostienen."
        )
    elif not d.get("aplica"):
        estado, texto = "NO_CONCLUYENTE", (
            "No hay materialidad aplicada en la fase, de modo que ninguna cuenta "
            "quedó seleccionada para revisión. El comparativo está calculado, pero "
            "sin umbral no hay alcance definido ni conclusión que sostener."
        )
    else:
        base = (
            f"Se compararon {d['total_cuentas']} cuentas a nivel de cuenta "
            f"(4 dígitos) y se seleccionaron {d['significativas']} para revisión, "
            "aplicando la materialidad de la fase y los criterios de selección "
            "vigentes. Los controles de cuadre ejecutados no arrojaron excepciones."
        )
        if sin_correr:
            base += (
                " Sin embargo, " + " y ".join(g["nombre"].lower() for g in sin_correr)
                + " no pudo ejecutarse, de modo que las cifras no están contrastadas "
                  "contra una fuente independiente."
            )
        if d.get("residuo_supera_umbral"):
            base += (
                " El conjunto de variaciones no seleccionadas supera la materialidad "
                "de la fase, por lo que el alcance debe ampliarse o dejarse constancia "
                "de por qué se acepta ese residuo."
            )
        estado = "RAZONABLE_CON_SALVEDADES" if (sin_correr or d.get("residuo_supera_umbral")) \
            else "RAZONABLE"
        texto = base

    return {"estado": estado, "texto": texto,
            "riesgo": riesgo["nivel"],
            "controles_evidencia": len(evidencia),
            "controles_fallidos": len(fallas),
            "controles_no_ejecutados": len(sin_correr)}


# ============================================================== ensamblado

def papel_trabajo(encargo_id: str, fase: str | None = None) -> dict:
    """El papel completo. Puede tardar: el cruce con movimientos consulta
    la evidencia de cada cuenta seleccionada."""
    enc = db.encargo(encargo_id)
    if not enc:
        return {"listo": False, "motivo": "El encargo no existe."}

    d = A.variaciones(encargo_id, fase)
    if not d["listo"]:
        sin_promover = d.get("sin_promover") or []
        return {
            "listo": False,
            "motivo": (
                "Hay balances cargados que nunca se promovieron: sus filas "
                "están en staging y no en el balance, así que sus saldos "
                "entrarían al comparativo como cero."
                if sin_promover else "Faltan balances para comparar."),
            "faltan": d["faltan"],
            "sin_promover": sin_promover,
        }

    contrato = _contrato_datos(encargo_id)
    previos = _controles_previos(enc, contrato)
    gates = _gates(encargo_id, d)
    riesgo = _riesgo(gates, previos, d)

    hallazgos = db.varios(
        """SELECT h.*, c.tipo FROM core.hallazgo h
           LEFT JOIN core.carga c ON c.id = h.carga_id
           WHERE h.encargo_id = %s ORDER BY h.detectado_en DESC LIMIT 200""",
        (encargo_id,),
    )

    return {
        "listo": True,
        "version": VERSION,
        "identificacion": {
            "cliente": enc["razon_social"], "nit": enc["nit"],
            "seudonimo": enc.get("seudonimo"),
            "encargo_id": encargo_id,
            "fecha_corte": enc["fecha_corte"],
            "cierre_anterior": enc["fecha_cierre_anterior"],
            "corte_anterior": enc["fecha_corte_anterior"],
            "responsable": enc["responsable"],
            "fase": d["fase"],
            "materialidad": d["materialidad"],
            "papel": "Revisión analítica de variaciones",
            "norma": "NIA 520 — Procedimientos analíticos",
        },
        "contrato_datos": contrato,
        "controles_previos": previos,
        "gates": gates,
        "cedula_sumaria": A.resumen_clases(encargo_id, "BAL_ACTUAL"),
        "comparativo": d,
        "hallazgos": hallazgos,
        "marcas": MARCAS,
        "riesgo": riesgo,
        "conclusion": _conclusion(gates, riesgo, d),
        "trazabilidad": {
            "eventos": db.bitacora(encargo_id=encargo_id, limite=300),
            "observaciones_ia": db.historia_observaciones_ia(enc["cliente_id"]),
        },
    }
