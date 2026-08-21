"""
Consultas de análisis sobre los datos ya cargados.

Igual que el resto: la base solo tiene tablas, aquí se arma todo.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import db
import ia


# =====================================================================
# EXPLORADOR DEL BALANCE
# =====================================================================

def carga_de(encargo_id: str, tipo: str) -> str | None:
    f = db.uno(
        "SELECT carga_id FROM core.encargo_insumo WHERE encargo_id=%s AND tipo=%s",
        (encargo_id, tipo),
    )
    return f["carga_id"] if f else None


def balance(encargo_id: str, tipo: str = "BAL_ACTUAL",
            nivel: str | None = None, padre: str | None = None,
            buscar: str | None = None, limite: int = 500) -> dict:
    """Filas del balance. Si viene `padre`, devuelve solo sus hijos directos."""
    cid = carga_de(encargo_id, tipo)
    if not cid:
        return {"carga_id": None, "filas": [], "total": 0}

    where = ["b.carga_id = %s"]
    args: list = [cid]

    if padre:
        # hijos directos: el siguiente nivel hacia abajo
        sig = db.uno(
            """SELECT nivel, digitos FROM core.nivel_cargable
               WHERE digitos > %s ORDER BY digitos LIMIT 1""",
            (len(padre),),
        )
        if not sig:
            return {"carga_id": cid, "filas": [], "total": 0}
        where.append("b.digitos = %s")
        args.append(sig["digitos"])
        where.append("left(b.codigo_puc, %s) = %s")
        args += [len(padre), padre]
    elif nivel:
        where.append("b.nivel = %s")
        args.append(nivel)

    if buscar:
        where.append("(b.codigo_puc LIKE %s OR b.nombre_cuenta ILIKE %s)")
        args += [f"{buscar}%", f"%{buscar}%"]

    sql = f"""
        SELECT b.codigo_puc, b.nombre_cuenta, b.nivel, b.digitos, b.clase,
               b.saldo_inicial, b.debito, b.credito, b.saldo_final,
               b.signo, b.saldo_natural,
               k.nombre AS clase_nombre,
               EXISTS (
                 SELECT 1 FROM core.balance h
                 WHERE h.carga_id = b.carga_id
                   AND h.digitos > b.digitos
                   AND left(h.codigo_puc, b.digitos) = b.codigo_puc
               ) AS tiene_hijos
        FROM core.balance b
        JOIN core.puc_clase k ON k.clase = b.clase
        WHERE {' AND '.join(where)}
        ORDER BY b.codigo_puc
        LIMIT {int(limite)}
    """
    filas = db.varios(sql, tuple(args))
    for f in filas:
        dif = (Decimal(str(f["saldo_inicial"])) + Decimal(str(f["debito"]))
               - Decimal(str(f["credito"])) - Decimal(str(f["saldo_final"])))
        f["descuadre_linea"] = dif.quantize(Decimal("0.01")) if dif != 0 else None
    return {"carga_id": cid, "filas": filas, "total": len(filas)}


def resumen_clases(encargo_id: str, tipo: str = "BAL_ACTUAL") -> list[dict]:
    cid = carga_de(encargo_id, tipo)
    if not cid:
        return []
    return db.varios(
        """SELECT b.clase, k.nombre AS clase_nombre, k.tipo_estado,
                  count(*) AS cuentas,
                  sum(b.saldo_natural) AS saldo
           FROM core.balance b
           JOIN core.puc_clase k ON k.clase = b.clase
           WHERE b.carga_id = %s AND b.nivel = 'Cuenta'
           GROUP BY b.clase, k.nombre, k.tipo_estado
           ORDER BY b.clase""",
        (cid,),
    )


# =====================================================================
# COMPARATIVO POR CUENTA
# =====================================================================

def _saldos_cuenta(carga_id: str) -> dict[str, dict]:
    if not carga_id:
        return {}
    filas = db.varios(
        """SELECT codigo_puc, nombre_cuenta, clase, saldo_natural, saldo_final
           FROM core.balance WHERE carga_id=%s AND nivel='Cuenta'""",
        (carga_id,),
    )
    return {f["codigo_puc"]: f for f in filas}


def variaciones(encargo_id: str, fase: str | None = None) -> dict:
    """Actual contra el comparativo que corresponde a cada clase.

      clases 1-3  ->  balance al cierre del año anterior
      clases 4-7  ->  balance al mismo corte del año anterior

    El umbral sale de la materialidad de la FASE indicada. Si esa fase no
    tiene valor o está sin aplicar, se devuelven todas las cuentas sin
    marcar ninguna: no se inventa un umbral.
    """
    act_id = carga_de(encargo_id, "BAL_ACTUAL")
    cie_id = carga_de(encargo_id, "BAL_CIERRE_ANTERIOR")
    cor_id = carga_de(encargo_id, "BAL_CORTE_ANTERIOR")

    faltan = [t for t, c in (("BAL_ACTUAL", act_id),
                             ("BAL_CIERRE_ANTERIOR", cie_id),
                             ("BAL_CORTE_ANTERIOR", cor_id)) if not c]
    if faltan:
        return {"listo": False, "faltan": faltan, "filas": []}

    par = db.parametros(encargo_id)
    fase = fase or par.get("fase_activa") or "PLANEACION"
    mat = db.materialidad_de_fase(encargo_id, fase)

    aplica = bool(mat and mat.get("aplicar") and mat.get("valor"))
    umbral = Decimal(mat["valor"]) if aplica else None
    pct_triv = Decimal(par.get("pct_trivialidad") or 5)
    trivial = (umbral * pct_triv / 100) if umbral else Decimal(0)
    pct_var = Decimal(par.get("pct_variacion") or 20)

    act = _saldos_cuenta(act_id)
    cie = _saldos_cuenta(cie_id)
    cor = _saldos_cuenta(cor_id)
    nombres = db.nombres_puc()

    filas = []
    for cod in sorted(set(act) | set(cie) | set(cor)):
        clase = cod[0]
        base = act.get(cod) or cie.get(cod) or cor.get(cod)
        comparativo = cie if clase <= "3" else cor
        regla = "Cierre anterior" if clase <= "3" else "Mismo corte del año anterior"

        if cod not in act and cod not in comparativo:
            continue

        sa = Decimal(act[cod]["saldo_natural"]) if cod in act else Decimal(0)
        sc = Decimal(comparativo[cod]["saldo_natural"]) if cod in comparativo else Decimal(0)
        var = (sa - sc).quantize(Decimal("0.01"))
        pctv = ((sa - sc) / abs(sc) * 100).quantize(Decimal("0.01")) if sc else None

        motivo = None
        if aplica:
            if abs(var) >= umbral:
                motivo = "Monto"
            elif sc == 0 and abs(sa) >= trivial:
                motivo = "Cuenta nueva"
            elif sa == 0 and abs(sc) >= trivial:
                motivo = "Cuenta cerrada"
            elif pctv is not None and abs(pctv) >= pct_var and abs(var) >= trivial:
                motivo = "Comportamiento"
            elif sa < 0 and abs(sa) >= trivial:
                motivo = "Naturaleza"

        filas.append({
            "cuenta": cod,
            "nombre": (base or {}).get("nombre_cuenta") or nombres.get(cod),
            "clase": clase,
            "regla": regla,
            "saldo_actual": sa,
            "saldo_comparativo": sc,
            "variacion": var,
            "variacion_pct": pctv,
            "motivo": motivo,
            "significativa": motivo is not None,
        })

    filas.sort(key=lambda f: abs(f["variacion"]), reverse=True)
    no_significativas = [f for f in filas if not f["significativa"]]
    residuo = sum(abs(f["variacion"]) for f in no_significativas)

    return {
        "listo": True,
        "faltan": [],
        "fase": fase,
        "aplica": aplica,
        "materialidad": mat,
        "umbral": umbral,
        "trivialidad": trivial,
        "pct_variacion": pct_var,
        "pct_trivialidad": pct_triv,
        "total_cuentas": len(filas),
        "significativas": sum(1 for f in filas if f["significativa"]),
        "residuo_no_seleccionado": residuo,
        "residuo_supera_umbral": bool(umbral and residuo > umbral),
        "desglose_no_seleccionado": (
            _desglose_residuo(no_significativas, trivial) if aplica else None
        ),
        "filas": filas,
    }


def _desglose_residuo(no_significativas: list[dict], trivial: Decimal) -> dict:
    """Por qué quedó cada cuenta fuera de la muestra: piso de ruido o
    variación que no llegó a cruzar el umbral. Es el argumento con datos
    para la nota de alcance, no solo el monto total.
    """
    triviales = [f for f in no_significativas if abs(f["variacion"]) < trivial]
    cercanas = [f for f in no_significativas if abs(f["variacion"]) >= trivial]
    cercanas.sort(key=lambda f: abs(f["variacion"]), reverse=True)

    return {
        "trivial": {
            "cuentas": len(triviales),
            "monto": sum(abs(f["variacion"]) for f in triviales),
        },
        "cerca_del_umbral": {
            "cuentas": len(cercanas),
            "monto": sum(abs(f["variacion"]) for f in cercanas),
            "mayores": [
                {"cuenta": f["cuenta"], "nombre": f["nombre"],
                 "variacion": f["variacion"], "variacion_pct": f["variacion_pct"]}
                for f in cercanas[:10]
            ],
        },
    }


# =====================================================================
# DETALLE DE UNA CUENTA
# =====================================================================

def detalle_cuenta(encargo_id: str, codigo: str) -> dict:
    """Composición de la cuenta y sus movimientos, si están cargados."""
    act_id = carga_de(encargo_id, "BAL_ACTUAL")
    hijos = db.varios(
        """SELECT codigo_puc, nombre_cuenta, nivel, saldo_inicial, debito,
                  credito, saldo_final, saldo_natural
           FROM core.balance
           WHERE carga_id=%s AND left(codigo_puc,%s)=%s AND digitos > %s
           ORDER BY codigo_puc""",
        (act_id, len(codigo), codigo, len(codigo)),
    ) if act_id else []

    mov_id = carga_de(encargo_id, "MOV_ACTUAL")
    movimientos, patrones = [], []
    if mov_id:
        movimientos = db.varios(
            """SELECT fecha, num_doc, secuencia, codigo_puc, tercero_nit,
                      tercero_nombre, descripcion, debito, credito
               FROM raw.movimiento_staging
               WHERE carga_id=%s AND left(codigo_puc,%s)=%s
               ORDER BY (debito::numeric + credito::numeric) DESC
               LIMIT 100""",
            (mov_id, len(codigo), codigo),
        )
        patrones = db.varios(
            """SELECT descripcion,
                      count(*) AS veces,
                      sum(debito::numeric - credito::numeric) AS neto
               FROM raw.movimiento_staging
               WHERE carga_id=%s AND left(codigo_puc,%s)=%s
               GROUP BY descripcion
               ORDER BY abs(sum(debito::numeric - credito::numeric)) DESC
               LIMIT 25""",
            (mov_id, len(codigo), codigo),
        )

    return {"codigo": codigo, "hijos": hijos,
            "movimientos": movimientos, "patrones": patrones}


# =====================================================================
# OBSERVACIONES DE IA
# =====================================================================

def _cop(v) -> str | None:
    """1234567.89 -> '1.234.567,89'. Se formatea acá, no en el modelo --
    si se le pide a la IA que la copie tal cual viene en el JSON (para no
    inventar cifras), copia también la notación con punto decimal sin
    separador de miles, que no es como se escribe un peso colombiano."""
    if v is None:
        return None
    n = Decimal(v)
    signo = "-" if n < 0 else ""
    entero, dec = f"{abs(n):.2f}".split(".")
    entero = f"{int(entero):,}".replace(",", ".")
    return f"{signo}{entero},{dec}"


def _patrones_cuenta(mov_id: str | None, codigo: str, limite: int = 8) -> list[dict]:
    if not mov_id:
        return []
    return db.varios(
        """SELECT descripcion,
                  count(*) AS veces,
                  sum(debito::numeric - credito::numeric) AS neto
           FROM raw.movimiento_staging
           WHERE carga_id=%s AND left(codigo_puc,%s)=%s
           GROUP BY descripcion
           ORDER BY abs(sum(debito::numeric - credito::numeric)) DESC
           LIMIT %s""",
        (mov_id, len(codigo), codigo, limite),
    )


def _auxiliares_variacion(act_id: str, comparativo_id: str, codigo: str,
                          variacion_cuenta: Decimal, limite: int = 8) -> list[dict]:
    """Composición a nivel Auxiliar (8 dígitos), comparando el mismo par de
    cargas que ya usa variaciones(). Le da a la IA en QUÉ auxiliar concreto
    está el cambio, no solo qué descripción de movimiento aparece más.

    El porcentaje de la variación total se calcula aquí, no por el modelo
    -- así puede citarlo como una cifra más del JSON, verificable, en vez
    de tener que sacar la cuenta él mismo."""
    def _saldos(carga_id: str | None) -> dict[str, dict]:
        if not carga_id:
            return {}
        filas = db.varios(
            """SELECT codigo_puc, nombre_cuenta, saldo_natural
               FROM core.balance
               WHERE carga_id=%s AND nivel='Auxiliar' AND left(codigo_puc,%s)=%s""",
            (carga_id, len(codigo), codigo),
        )
        return {f["codigo_puc"]: f for f in filas}

    act = _saldos(act_id)
    comp = _saldos(comparativo_id)

    crudas = []
    for cod in set(act) | set(comp):
        sa = Decimal(act[cod]["saldo_natural"]) if cod in act else Decimal(0)
        sc = Decimal(comp[cod]["saldo_natural"]) if cod in comp else Decimal(0)
        nombre = (act.get(cod) or comp[cod])["nombre_cuenta"]
        var = (sa - sc).quantize(Decimal("0.01"))
        pct = ((var / variacion_cuenta) * 100).quantize(Decimal("0.01")) \
            if variacion_cuenta else None
        crudas.append((cod, nombre, sa, sc, var, pct))

    crudas.sort(key=lambda t: abs(t[4]), reverse=True)   # t[4] = var, sin formatear
    return [
        {"codigo": cod, "nombre": nombre,
         "saldo_actual": _cop(sa), "saldo_comparativo": _cop(sc),
         "variacion": _cop(var), "pct_de_la_variacion_total": pct}
        for cod, nombre, sa, sc, var, pct in crudas[:limite]
    ]


def _entrada_observacion(fila: dict, patrones: list[dict],
                         auxiliares: list[dict]) -> dict:
    """Solo lo ya calculado: nada que el modelo tenga que inferir con
    aritmética propia. Sin razón social ni NIT del cliente -- no le hace
    falta al modelo para explicar la variación de una cuenta."""
    return {
        "moneda": "COP (pesos colombianos)",
        "cuenta": fila["cuenta"],
        "nombre_cuenta": fila["nombre"],
        "regla_comparativo": fila["regla"],
        "saldo_actual": _cop(fila["saldo_actual"]),
        "saldo_comparativo": _cop(fila["saldo_comparativo"]),
        "variacion": _cop(fila["variacion"]),
        "variacion_pct": fila["variacion_pct"],
        "motivo_seleccion": fila["motivo"],
        "patrones_de_movimiento": [
            {"descripcion": p["descripcion"], "veces": p["veces"], "neto": _cop(p["neto"])}
            for p in patrones
        ],
        "composicion_auxiliar": auxiliares,
    }


def _entrada_para(d: dict, encargo_id: str, fila: dict) -> dict:
    act_id = carga_de(encargo_id, "BAL_ACTUAL")
    comparativo_id = (carga_de(encargo_id, "BAL_CIERRE_ANTERIOR") if fila["clase"] <= "3"
                      else carga_de(encargo_id, "BAL_CORTE_ANTERIOR"))
    mov_id = carga_de(encargo_id, "MOV_ACTUAL")
    patrones = _patrones_cuenta(mov_id, fila["cuenta"])
    auxiliares = _auxiliares_variacion(act_id, comparativo_id, fila["cuenta"],
                                       fila["variacion"])
    return _entrada_observacion(fila, patrones, auxiliares)


def _generar_y_guardar(d: dict, encargo_id: str, cliente_id: str, fase: str,
                       fila: dict, instruccion: str | None = None,
                       usuario: str | None = None) -> dict:
    """Redacta y persiste. Si viene `instruccion`, se le pasa al modelo
    junto con el texto de la versión anterior, para que ajuste en vez de
    empezar de cero -- y queda una versión nueva, sin borrar la previa."""
    previo = None
    if instruccion:
        anterior = db.observacion_ia_ultima(encargo_id, fase, fila["cuenta"])
        previo = anterior["texto"] if anterior else None

    entrada = _entrada_para(d, encargo_id, fila)
    r = ia.redactar_observacion(entrada, instruccion=instruccion, previo=previo)

    if r.get("error"):
        # Un fallo del modelo no se guarda como si fuera un análisis: se
        # devuelve para mostrarlo y que se pueda reintentar.
        return {"codigo_puc": fila["cuenta"], "version": None, **r}

    return db.guardar_observacion_ia(
        cliente_id=cliente_id, encargo_id=encargo_id, fase=fase,
        codigo_puc=fila["cuenta"], texto=r["texto"], verificado=r["verificado"],
        cifras=r["cifras_no_verificadas"], entrada=entrada,
        instruccion=instruccion, modelo=ia.modelo_actual(), usuario=usuario,
    )


def observaciones_guardadas(encargo_id: str, fase: str) -> list[dict]:
    """Lo ya redactado para esta fase, sin volver a llamar al modelo."""
    return db.observaciones_ia_vigentes(encargo_id, fase)


def historia_observaciones(encargo_id: str, codigo: str | None = None) -> list[dict]:
    """El repositorio completo del CLIENTE dueño de este encargo: todas
    las versiones, de todos los encargos y fases."""
    enc = db.encargo(encargo_id)
    if not enc:
        return []
    return db.historia_observaciones_ia(enc["cliente_id"], codigo)


def observacion_cuenta(encargo_id: str, fase: str, codigo: str,
                       instruccion: str | None = None,
                       usuario: str | None = None) -> dict | None:
    """Genera (o reajusta) y guarda la observación de una cuenta. None si
    la cuenta no está entre las variaciones de esta fase."""
    d = variaciones(encargo_id, fase)
    if not d["listo"] or not d["aplica"]:
        return None
    fila = next((f for f in d["filas"] if f["cuenta"] == codigo), None)
    if fila is None:
        return None
    enc = db.encargo(encargo_id)
    return _generar_y_guardar(d, encargo_id, enc["cliente_id"], fase, fila,
                              instruccion, usuario)


def observaciones_lote(encargo_id: str, fase: str, codigos: list[str],
                       usuario: str | None = None) -> list[dict]:
    """Varias observaciones a la vez, EN PARALELO -- pensado para pedirse
    en lotes chicos desde el frontend (ej. de 5 en 5), así el tiempo de
    la petición es el de la cuenta más lenta del lote, no la suma de
    todas. Generarlas todas de una en secuencia fue justo lo que causó
    el 504 con un proveedor en la nube."""
    d = variaciones(encargo_id, fase)
    if not d["listo"] or not d["aplica"]:
        return []
    por_codigo = {f["cuenta"]: f for f in d["filas"]}
    seleccion = [por_codigo[c] for c in codigos if c in por_codigo]
    if not seleccion:
        return []

    enc = db.encargo(encargo_id)
    cliente_id = enc["cliente_id"]

    def _una(fila: dict) -> dict:
        return _generar_y_guardar(d, encargo_id, cliente_id, fase, fila,
                                  usuario=usuario)

    with ThreadPoolExecutor(max_workers=len(seleccion)) as ex:
        return list(ex.map(_una, seleccion))


