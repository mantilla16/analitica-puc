"""
Consultas de análisis sobre los datos ya cargados.

Igual que el resto: la base solo tiene tablas, aquí se arma todo.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import db
import ia
import reglas as R


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
        # Hijos directos: el siguiente nivel hacia abajo CON DATOS reales en
        # este balance, no el siguiente nivel declarado en nivel_cargable.
        # Si el archivo trae niveles salteados -- SAP suele saltar de Clase
        # a Cuenta sin pasar por Grupo -- preguntarle a nivel_cargable
        # devolvia el nivel teorico (Grupo=2 digitos) y el drill mostraba
        # vacio aunque hubiera 19 cuentas colgando de esa clase.
        sig = db.uno(
            """SELECT min(digitos) AS digitos
               FROM core.balance
               WHERE carga_id=%s AND digitos>%s
                 AND left(codigo_puc, %s) = %s""",
            (cid, len(padre), len(padre), padre),
        )
        if not sig or sig["digitos"] is None:
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
               -- Dos cifras distintas y la vista mostraba la equivocada bajo
               -- el rotulo "Naturaleza": `saldo_natural` es la COMPARABLE (la
               -- que suma cero) y `saldo_naturaleza` la que dice de que lado
               -- esta el saldo frente a su naturaleza. Con la convencion del
               -- catalogo coinciden; con la del archivo -- DOXA -- difieren en
               -- signo, y pintaba en rojo como "al reves" todos los pasivos,
               -- el patrimonio y los ingresos, que estaban normales.
               coalesce(b.saldo_naturaleza, b.saldo_natural) AS saldo_naturaleza,
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
    conv = db.uno("SELECT convencion_signo FROM core.carga WHERE id=%s", (cid,))
    return {"carga_id": cid, "filas": filas, "total": len(filas),
            "convencion_signo": (conv or {}).get("convencion_signo")}


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
        """SELECT codigo_puc, nombre_cuenta, clase, signo, saldo_natural,
                  coalesce(saldo_naturaleza, saldo_natural) AS saldo_naturaleza,
                  saldo_final
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
        return {"listo": False, "faltan": faltan, "sin_promover": [],
                "filas": []}

    par = db.parametros(encargo_id)
    fase = fase or par.get("fase_activa") or "PLANEACION"
    fila_mat = db.materialidad_de_fase(encargo_id, fase)
    res = R.resolver_materialidad(fila_mat)

    # El umbral de "Monto" es la materialidad de DESEMPENO, no la global.
    # Antes se usaba la global directo, que equivale a un desempeno del
    # 100%: deja fuera del alcance justo las variaciones que, sumadas por
    # debajo del umbral, pueden llegar a ser materiales.
    #
    # Los dos criterios se pueden apagar por encargo. Con el error trivial
    # apagado vale 0, así que las comparaciones `>= trivial` dejan de
    # filtrar y el criterio de porcentaje queda absoluto: cualquier
    # variación que cruce el porcentaje se reporta, por pequeña que sea.
    usa_var = par.get("aplica_variacion", True)
    usa_triv = par.get("aplica_trivialidad", True)
    aplica = res["aplica"]
    umbral, trivial = R.umbrales_seleccion(res, usa_triv)
    pct_var = Decimal(par.get("pct_variacion") or 20)
    # Se conserva la llave para los lectores viejos (conclusion, excel): es
    # el % del trivial sobre la global de ESTA fase, no ya del encargo.
    pct_triv = res["trivial"]["pct"]

    # Se conservan todas las llaves de la fila (nombre, valor, aplicar,
    # aprobado_por...) que ya leian papel y frontend, y se agregan las tres
    # cifras resueltas y la fase.
    mat = dict(fila_mat or {}, fase=fase, **{
        "global": res["global"], "desempeno": res["desempeno"],
        "trivial": res["trivial"], "aplica": aplica})

    act = _saldos_cuenta(act_id)
    cie = _saldos_cuenta(cie_id)
    cor = _saldos_cuenta(cor_id)

    # Una carga puede existir y estar apuntada por el checklist sin haberse
    # promovido nunca: queda en staging y `core.balance` no tiene una sola
    # fila suya. Si se deja pasar, sus saldos entran al comparativo como
    # cero y el resultado sale completo, coherente y falso -- toda variación
    # termina siendo el saldo del comparativo con el signo cambiado, y los
    # controles internos lo aprueban porque cero cuadra con cero.
    #
    # Es el error silencioso más caro que puede dar este módulo, así que no
    # se calcula sobre datos que no están: se detiene y se dice cuál falta.
    sin_promover = [t for t, s in (("BAL_ACTUAL", act),
                                   ("BAL_CIERRE_ANTERIOR", cie),
                                   ("BAL_CORTE_ANTERIOR", cor)) if not s]
    if sin_promover:
        return {"listo": False, "faltan": sin_promover,
                "sin_promover": sin_promover, "filas": []}

    nombres = db.nombres_puc()

    filas = []
    for cod in sorted(set(act) | set(cie) | set(cor)):
        clase = cod[0]
        base = act.get(cod) or cie.get(cod) or cor.get(cod)
        comparativo = cie if R.compara_contra_cierre(clase) else cor
        regla = "Cierre anterior" if R.compara_contra_cierre(clase) else "Mismo corte del año anterior"

        if cod not in act and cod not in comparativo:
            continue

        # La variación se calcula sobre `saldo_naturaleza` -- el saldo con el
        # signo de su propia naturaleza -- y NO sobre la cifra comparable.
        #
        # La comparable sirve para probar que el balance cuadra (suma cero),
        # pero su signo depende de cómo venga el archivo del cliente: con la
        # convención del catálogo un pasivo sale positivo y con la del
        # archivo sale negativo. Usarla aquí hacía que el MISMO hecho
        # económico saliera con signo opuesto según el ERP que exportó el
        # archivo: 2505 SALARIOS POR PAGAR bajando de 140 a 8 millones se
        # leía como "aumento del 94%" en DOXA y como "disminución del 94%" en
        # LIQUITECH. Con `saldo_naturaleza`, positivo siempre significa "la
        # cuenta se comporta como debe", así que subir es subir en cualquier
        # cliente: la obligación por salarios DISMINUYÓ 94%.
        #
        # No altera el alcance: `motivo_seleccion` mide magnitudes
        # (`abs(var)`, `abs(pctv)`) y compara contra cero, todo insensible al
        # signo. Lo único que cambia es la DIRECCIÓN que se reporta, que es
        # justo lo que estaba al revés.
        sa = Decimal(act[cod]["saldo_naturaleza"]) if cod in act else Decimal(0)
        sc = Decimal(comparativo[cod]["saldo_naturaleza"]) if cod in comparativo else Decimal(0)
        var = (sa - sc).quantize(Decimal("0.01"))
        pctv = ((sa - sc) / abs(sc) * 100).quantize(Decimal("0.01")) if sc else None

        nat = sa if cod in act else sc
        motivo = R.motivo_seleccion(sa, sc, var, pctv,
                                    umbral if aplica else None,
                                    trivial, pct_var, usa_var, naturaleza=nat)

        filas.append({
            "cuenta": cod,
            "nombre": (base or {}).get("nombre_cuenta") or nombres.get(cod),
            "clase": clase,
            "regla": regla,
            # De qué lado está el saldo normal de la cuenta. Los saldos de
            # esta fila van EN SU NATURALEZA (positivo = del lado normal),
            # y sin decir cuál es ese lado un pasivo en positivo se lee como
            # débito: así lo leyó el equipo en el primer papel de un cliente
            # que exporta los créditos en negativo.
            "naturaleza": "C" if int((base or {}).get("signo") or 1) < 0 else "D",
            "saldo_actual": sa,
            "saldo_comparativo": sc,
            "variacion": var,
            "variacion_pct": pctv,
            "motivo": motivo,
            "significativa": motivo is not None,
        })

    # Orden por código PUC: es como se recorre un balance y como se revisa
    # una cédula. Antes iba por variación descendente, que servía para
    # "lo más grande primero" pero desordenaba la lectura contable.
    filas.sort(key=lambda f: f["cuenta"])

    # Exclusiones del auditor: la cuenta sale de `filas` (no se selecciona
    # ni suma al residuo) y pasa a `excluidas`, con su motivo, para que el
    # papel la declare. Se separa en lugar de marcarla porque todo lo que
    # recorre `filas` (gates, cedula, excel, IA) debe ignorarla sin tener
    # que saber que existe la exclusion.
    exclusiones = db.cuentas_excluidas(encargo_id)
    excluidas = []
    if exclusiones:
        quedan = []
        for f in filas:
            e = R.exclusion_de(f["cuenta"], exclusiones)
            if e:
                excluidas.append({**f, "significativa": False,
                                  "motivo_original": f["motivo"], "motivo": None,
                                  "exclusion": e})
            else:
                quedan.append(f)
        filas = quedan
    variacion_excluida = sum(abs(f["variacion"]) for f in excluidas)

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
        "aplica_variacion": usa_var,
        "aplica_trivialidad": usa_triv,
        "total_cuentas": len(filas),
        "significativas": sum(1 for f in filas if f["significativa"]),
        # Sale de R.MOTIVOS y no de una lista repetida aquí: si algún día se
        # agrega un motivo, aparece solo en vez de faltar en silencio.
        "por_motivo": {m: sum(1 for f in filas if f["motivo"] == m)
                       for m in R.MOTIVOS},
        "residuo_no_seleccionado": residuo,
        "residuo_supera_umbral": bool(umbral and residuo > umbral),
        "desglose_no_seleccionado": (
            _desglose_residuo(no_significativas, trivial) if aplica else None
        ),
        "filas": filas,
        "exclusiones": exclusiones,
        "excluidas": excluidas,
        "variacion_excluida": variacion_excluida,
        # Excluir no es gratis: si lo que se saco del analisis por si solo
        # supera la materialidad de desempeño, el papel tiene que decirlo.
        "excluidas_superan_umbral": bool(umbral and variacion_excluida > umbral),
    }


def _desglose_residuo(no_significativas: list[dict], trivial: Decimal) -> dict:
    """Por qué quedó cada cuenta fuera de la muestra: error trivial o
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
            "movimientos": movimientos, "patrones": patrones,
            "movimientos_vs_anterior": _comparacion_de_cuenta(
                movimientos_comparados(encargo_id), codigo)}


# =====================================================================
# MOVIMIENTOS CONTRA EL AÑO ANTERIOR
# =====================================================================

def _comparar_cargas(act_id: str | None, ant_id: str | None,
                     fecha_corte, fecha_corte_anterior, c=None) -> dict:
    """El nucleo de movimientos_comparados, separado de la lectura del
    encargo para poder validarlo con cargas sembradas (validar_motor pasa
    `c`, su conexion con la transaccion sin confirmar)."""
    (a_ini, a_fin), (b_ini, b_fin) = R.ventanas_movimientos(
        fecha_corte, fecha_corte_anterior)
    base = {"ventana_actual": {"desde": a_ini.isoformat(), "hasta": a_fin.isoformat()},
            "ventana_anterior": {"desde": b_ini.isoformat(), "hasta": b_fin.isoformat()}}

    faltan = [n for n, cid in (("los movimientos del periodo (MOV_ACTUAL)", act_id),
                               ("los movimientos del año anterior (MOV_ANTERIOR)", ant_id))
              if not cid]
    if faltan:
        # No se compara contra ceros: un año anterior sin archivo no es un
        # año sin movimientos, y tratarlo asi haria ver cada cuenta como
        # "crecio 100%".
        return {"disponible": False,
                "motivo": f"No se cargaron {' ni '.join(faltan)}: la comparación "
                          "de movimientos contra el año anterior no se ejecutó.",
                **base, "por_cuenta": {}}

    actual = db.movimientos_por_cuenta(act_id, a_ini, a_fin, c=c)
    anterior = db.movimientos_por_cuenta(ant_id, b_ini, b_fin, c=c)
    return {"disponible": True, "motivo": None, **base,
            "por_cuenta": R.comparar_movimientos(actual, anterior)}


def movimientos_comparados(encargo_id: str) -> dict:
    """Movimientos del periodo (1-ene al corte) contra la MISMA ventana del
    año anterior, por cuenta. Dos queries agrupadas en total, una por carga,
    sin importar cuantas cuentas haya.

    No se llama desde variaciones(): ese calculo corre en cada pantalla y
    esta comparacion solo la necesitan quienes la muestran.
    """
    enc = db.encargo(encargo_id)
    if not enc:
        return {"disponible": False, "motivo": "El encargo no existe.",
                "ventana_actual": None, "ventana_anterior": None,
                "por_cuenta": {}}
    return _comparar_cargas(carga_de(encargo_id, "MOV_ACTUAL"),
                            carga_de(encargo_id, "MOV_ANTERIOR"),
                            enc["fecha_corte"], enc["fecha_corte_anterior"])


def _comparacion_de_cuenta(mc: dict, codigo: str) -> dict:
    """La comparacion de UNA cuenta, a partir del dict ya calculado. El
    calculo se hace una vez y se reparte, nunca por cuenta."""
    return {"disponible": mc["disponible"], "motivo": mc["motivo"],
            "ventana_actual": mc["ventana_actual"],
            "ventana_anterior": mc["ventana_anterior"],
            "cuenta": (mc.get("por_cuenta") or {}).get(codigo[:4])}


def _ventana_txt(v: dict | None) -> str | None:
    return f"{v['desde']} a {v['hasta']}" if v else None


def _movimientos_para_ia(mc: dict | None, codigo: str) -> dict:
    """La comparacion de una cuenta, con las cifras ya en formato de pesos.

    Si no esta disponible solo se dice eso: sin cifras no hay nada que el
    modelo pueda copiar, y la regla del prompt le prohibe mencionar el año
    anterior en ese caso.
    """
    if not mc or not mc.get("disponible"):
        return {"disponible": False,
                "motivo": (mc or {}).get("motivo")
                or "No hay comparación de movimientos contra el año anterior."}
    x = (mc.get("por_cuenta") or {}).get(codigo[:4])
    salida = {"disponible": True,
              "ventana_actual": _ventana_txt(mc["ventana_actual"]),
              "ventana_anterior": _ventana_txt(mc["ventana_anterior"])}
    if not x:
        # Disponible pero sin una sola linea en ninguna de las dos ventanas:
        # es un dato (la cuenta no se movio), no una ausencia.
        salida.update({"movimientos_actual": 0, "movimientos_anterior": 0,
                       "neto_actual": _cop(0), "neto_anterior": _cop(0)})
        return salida
    salida.update({
        "movimientos_actual": x["actual"]["n"],
        "movimientos_anterior": x["anterior"]["n"],
        "debito_actual": _cop(x["actual"]["debito"]),
        "credito_actual": _cop(x["actual"]["credito"]),
        "neto_actual": _cop(x["actual"]["neto"]),
        "debito_anterior": _cop(x["anterior"]["debito"]),
        "credito_anterior": _cop(x["anterior"]["credito"]),
        "neto_anterior": _cop(x["anterior"]["neto"]),
        "diferencia_neto": _cop(x["delta_neto"]),
        "diferencia_neto_pct": x["delta_neto_pct"],
        "diferencia_movimientos": x["delta_n"],
    })
    return salida


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
    de tener que sacar la cuenta él mismo.

    El nivel se elige por cuenta y tiene que estar COMPLETO en las dos
    cargas: sus filas bajo esta cuenta deben sumar el saldo de la cuenta.
    Antes se tomaba el nivel más profundo de cada archivo, por separado. Al
    balance de mayo 2026 de un cliente se le coló UNA cuenta de 9 dígitos
    (135518100) entre las de 8 y 10: ese archivo pasó a tener "9" como nivel
    más granular, el comparativo seguía en 8, y cada auxiliar salía con
    saldo actual cero y variación igual a todo su saldo anterior. La 3710,
    que no se movió un peso, mostraba una variación de 1.004.507.366 en su
    auxiliar, y la IA la redactaba como hecho. Que el nivel cuadre con la
    cuenta en los dos lados es lo que garantiza que se comparan los mismos
    códigos, y se comprueba en vez de suponerse.
    """
    def _filas(carga_id: str | None) -> tuple[dict[str, dict], Decimal]:
        if not carga_id:
            return {}, Decimal(0)
        # Misma base que la cuenta: el porcentaje es var/variacion_cuenta,
        # y con bases de signo distinto el cociente saldria invertido.
        filas = db.varios(
            """SELECT codigo_puc, nombre_cuenta, digitos,
                      coalesce(saldo_naturaleza, saldo_natural) AS saldo_natural
               FROM core.balance
               WHERE carga_id=%s AND left(codigo_puc,%s)=%s
                 AND digitos >= %s""",
            (carga_id, len(codigo), codigo, len(codigo)),
        )
        propia = next((f for f in filas if f["codigo_puc"] == codigo), None)
        total = Decimal(propia["saldo_natural"]) if propia else Decimal(0)
        return ({f["codigo_puc"]: f for f in filas
                 if f["digitos"] > len(codigo)}, total)

    todas_act, total_act = _filas(act_id)
    todas_comp, total_comp = _filas(comparativo_id)

    def _completo(filas: dict[str, dict], total: Decimal, d: int) -> bool:
        suma = sum((Decimal(f["saldo_natural"]) for f in filas.values()
                    if f["digitos"] == d), Decimal(0))
        return abs(suma - total) <= Decimal("1.00")

    niveles = sorted({f["digitos"] for f in todas_act.values()}
                     | {f["digitos"] for f in todas_comp.values()},
                     reverse=True)
    nivel = next((d for d in niveles
                  if _completo(todas_act, total_act, d)
                  and _completo(todas_comp, total_comp, d)), None)
    if nivel is None:
        # Ningún nivel reconstruye la cuenta en los dos cortes: mostrar un
        # desglose sería inventar de dónde viene la variación.
        return []

    act = {k: f for k, f in todas_act.items() if f["digitos"] == nivel}
    comp = {k: f for k, f in todas_comp.items() if f["digitos"] == nivel}

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


def _direccion(var: Decimal) -> str:
    """Aumentó o disminuyó, sobre el saldo en su propia naturaleza."""
    v = Decimal(str(var or 0))
    if v > 0:
        return "aumento (la cuenta creció respecto a su comparativo)"
    if v < 0:
        return "disminucion (la cuenta se redujo respecto a su comparativo)"
    return "sin cambio"


def _entrada_observacion(fila: dict, patrones: list[dict],
                         auxiliares: list[dict],
                         movimientos_vs_anterior: dict | None = None) -> dict:
    """Solo lo ya calculado: nada que el modelo tenga que inferir con
    aritmética propia. Sin razón social ni NIT del cliente -- no le hace
    falta al modelo para explicar la variación de una cuenta.

    `movimientos_vs_anterior` llega ya formateado (_movimientos_para_ia).
    Es opcional para que observaciones_guardadas pueda armar la entrada
    solo para cotejar cifras, sin pagar la comparacion."""
    return {
        "moneda": "COP (pesos colombianos)",
        "cuenta": fila["cuenta"],
        "nombre_cuenta": fila["nombre"],
        "regla_comparativo": fila["regla"],
        "saldo_actual": _cop(fila["saldo_actual"]),
        "saldo_comparativo": _cop(fila["saldo_comparativo"]),
        "variacion": _cop(fila["variacion"]),
        "variacion_pct": fila["variacion_pct"],
        # La dirección se calcula aquí y se dice en palabras. Dejar que el
        # modelo la deduzca del signo es pedirle una operación aritmetica
        # sobre una convención contable, y es donde se equivocaba: llamaba
        # "aumento" a un pasivo que se pagó.
        "direccion": _direccion(fila["variacion"]),
        "motivo_seleccion": fila["motivo"],
        "patrones_de_movimiento": [
            {"descripcion": p["descripcion"], "veces": p["veces"], "neto": _cop(p["neto"])}
            for p in patrones
        ],
        "composicion_auxiliar": auxiliares,
        "movimientos_vs_anterior": (
            movimientos_vs_anterior if movimientos_vs_anterior is not None
            else {"disponible": False,
                  "motivo": "No se consultó la comparación de movimientos."}),
    }


def _entrada_para(d: dict, encargo_id: str, fila: dict,
                  mc: dict | None = None) -> dict:
    """`mc` es movimientos_comparados ya calculado. En lote se calcula una
    vez y se reparte; si no llega, se calcula aqui (una cuenta suelta)."""
    act_id = carga_de(encargo_id, "BAL_ACTUAL")
    comparativo_id = (carga_de(encargo_id, "BAL_CIERRE_ANTERIOR") if R.compara_contra_cierre(fila["clase"])
                      else carga_de(encargo_id, "BAL_CORTE_ANTERIOR"))
    mov_id = carga_de(encargo_id, "MOV_ACTUAL")
    patrones = _patrones_cuenta(mov_id, fila["cuenta"])
    auxiliares = _auxiliares_variacion(act_id, comparativo_id, fila["cuenta"],
                                       fila["variacion"])
    if mc is None:
        mc = movimientos_comparados(encargo_id)
    return _entrada_observacion(fila, patrones, auxiliares,
                                _movimientos_para_ia(mc, fila["cuenta"]))


def _generar_y_guardar(d: dict, encargo_id: str, cliente_id: str, fase: str,
                       fila: dict, instruccion: str | None = None,
                       usuario: str | None = None,
                       mc: dict | None = None) -> dict:
    """Redacta y persiste. Si viene `instruccion`, se le pasa al modelo
    junto con el texto de la versión anterior, para que ajuste en vez de
    empezar de cero -- y queda una versión nueva, sin borrar la previa."""
    previo = None
    if instruccion:
        anterior = db.observacion_ia_ultima(encargo_id, fase, fila["cuenta"])
        previo = anterior["texto"] if anterior else None

    entrada = _entrada_para(d, encargo_id, fila, mc)
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


def evidencia_cuenta(encargo_id: str, fase: str, codigo: str) -> dict:
    """Los datos crudos detrás de una cuenta, para contrastar lo que
    afirma la IA: en qué auxiliares está el cambio, qué se movió y --
    lo más importante -- si la suma de los movimientos realmente explica
    la variación.

    Ese cuadre es el control que faltaba: si los movimientos del periodo
    no reconstruyen la diferencia entre los dos saldos, entonces ninguna
    narrativa sobre esa cuenta se sostiene, la haya escrito un modelo o
    una persona.
    """
    d = variaciones(encargo_id, fase)
    if not d["listo"]:
        return {"listo": False, "faltan": d["faltan"]}
    fila = next((f for f in d["filas"] if f["cuenta"] == codigo), None)
    if fila is None:
        return {"listo": False, "faltan": []}

    act_id = carga_de(encargo_id, "BAL_ACTUAL")
    comparativo_id = (carga_de(encargo_id, "BAL_CIERRE_ANTERIOR") if R.compara_contra_cierre(fila["clase"])
                      else carga_de(encargo_id, "BAL_CORTE_ANTERIOR"))
    mov_id = carga_de(encargo_id, "MOV_ACTUAL")

    signo = (db.uno(
        """SELECT signo FROM core.balance
           WHERE carga_id=%s AND codigo_puc=%s AND nivel='Cuenta'""",
        (act_id, codigo),
    ) or {}).get("signo", 1)

    movimientos, patrones, totales = [], [], None
    if mov_id:
        patrones = db.varios(
            """SELECT descripcion, count(*) AS veces,
                      sum(debito::numeric)  AS debito,
                      sum(credito::numeric) AS credito,
                      sum(debito::numeric - credito::numeric) AS neto
               FROM raw.movimiento_staging
               WHERE carga_id=%s AND left(codigo_puc,%s)=%s
               GROUP BY descripcion
               ORDER BY abs(sum(debito::numeric - credito::numeric)) DESC
               LIMIT 40""",
            (mov_id, len(codigo), codigo),
        )
        movimientos = db.varios(
            """SELECT fecha, num_doc, secuencia, codigo_puc, tercero_nit,
                      tercero_nombre, descripcion,
                      debito::numeric AS debito, credito::numeric AS credito
               FROM raw.movimiento_staging
               WHERE carga_id=%s AND left(codigo_puc,%s)=%s
               ORDER BY abs(debito::numeric - credito::numeric) DESC
               LIMIT 100""",
            (mov_id, len(codigo), codigo),
        )
        totales = db.uno(
            """SELECT count(*) AS n,
                      coalesce(sum(debito::numeric),0)  AS debito,
                      coalesce(sum(credito::numeric),0) AS credito
               FROM raw.movimiento_staging
               WHERE carga_id=%s AND left(codigo_puc,%s)=%s""",
            (mov_id, len(codigo), codigo),
        )

    return {
        "listo": True,
        "cuenta": codigo,
        "nombre": fila["nombre"],
        "fila": fila,
        "auxiliares": _auxiliares_variacion(act_id, comparativo_id, codigo,
                                            fila["variacion"], limite=50),
        "patrones": patrones,
        "movimientos": movimientos,
        "cuadre": _cuadre_movimientos(fila, totales, signo),
        # Las mismas cifras que recibio la IA, para contrastar lo que afirme
        # sobre el año anterior.
        "movimientos_vs_anterior": _movimientos_para_ia(
            movimientos_comparados(encargo_id), codigo),
    }


# Dos exportes del mismo mayor pueden diferir en centavos por cómo cada uno
# redondea. Sin tolerancia, un centavo sobre siete mil millones tumba el papel
# entero -- y un control que falla por redondeos enseña a ignorarlo, que es
# peor que no tenerlo.
#
# Un peso por cuenta: absorbe el redondeo entre dos exportes y deja fallar
# cualquier omisión real, que nunca es de centavos. La diferencia NO se calla:
# se reporta como cuadre con diferencia de redondeo, con su cifra. Una
# tolerancia silenciosa sería exactamente el error que este papel persigue.
TOLERANCIA_CUADRE = Decimal("1.00")


def _cuadre_movimientos(fila: dict, totales: dict | None, signo: int) -> dict | None:
    """¿Los movimientos del periodo explican la cifra que se está mirando?

    Depende de la clase, y no por capricho:
      · Clases 1-3 se comparan contra el cierre de diciembre, que es el
        saldo inicial del periodo. Entonces débitos menos créditos debe
        reproducir la VARIACIÓN.
      · Clases 4-7 arrancan el año en cero y se comparan contra el mismo
        corte del año pasado. Los movimientos del año en curso explican
        el SALDO ACTUAL, no la diferencia contra el año anterior.
    """
    # Sin archivo de movimientos no hay contra qué contrastar. Con archivo y
    # cero líneas para la cuenta SÍ hay respuesta: neto cero. Si la cifra
    # también es cero, cuadra; si no, faltan movimientos -- que es justo lo
    # que pasa con las cuentas que quedaron después del corte de un exporte
    # truncado, y callarlo las dejaba pasar por "sin datos".
    if not totales:
        return None

    neto = (Decimal(totales["debito"]) - Decimal(totales["credito"])) * signo
    if R.compara_contra_cierre(fila["clase"]):
        contra, esperado = "la variación", Decimal(fila["variacion"])
    else:
        contra, esperado = "el saldo actual", Decimal(fila["saldo_actual"])

    dif = (neto - esperado).quantize(Decimal("0.01"))
    dentro = abs(dif) <= TOLERANCIA_CUADRE
    return {
        "movimientos": totales["n"],
        "debito": _cop(totales["debito"]),
        "credito": _cop(totales["credito"]),
        "neto": _cop(neto),
        "contra": contra,
        "esperado": _cop(esperado),
        "diferencia": _cop(dif),
        "cuadra": dentro,
        # Cuadra dentro de la tolerancia, pero no es exacto. Se distingue para
        # que el papel pueda decirlo en vez de presentarlo como cuadre limpio.
        "por_redondeo": dif != 0 and dentro,
        "tolerancia": _cop(TOLERANCIA_CUADRE),
    }


CIFRAS_DE_LA_OBSERVACION = ("saldo_actual", "saldo_comparativo", "variacion",
                            "variacion_pct")


def observaciones_guardadas(encargo_id: str, fase: str) -> list[dict]:
    """Lo ya redactado para esta fase, sin volver a llamar al modelo.

    Cada observación se coteja contra las cifras de HOY. Un texto redactado
    sobre otras cifras no es solo viejo: puede afirmar lo contrario de lo
    que pasó. Al corregir la base de la variación, todas las observaciones
    de un cliente cuyo archivo viene con los signos aplicados quedaron
    diciendo "aumento" sobre cuentas que disminuyeron. Callarlo dejaría un
    papel firmado con una explicación al revés.
    """
    guardadas = db.observaciones_ia_vigentes(encargo_id, fase)
    if not guardadas:
        return []

    d = variaciones(encargo_id, fase)
    hoy = {f["cuenta"]: f for f in d.get("filas", [])}

    for o in guardadas:
        entrada = o.pop("entrada", None) or {}
        fila = hoy.get(o["codigo_puc"])
        cambiadas = []
        if fila:
            actual = _entrada_observacion(fila, [], [])
            for k in CIFRAS_DE_LA_OBSERVACION:
                antes, ahora = entrada.get(k), actual.get(k)
                if antes is not None and str(antes) != str(ahora):
                    cambiadas.append({"cifra": k, "antes": antes, "ahora": ahora})
        o["desactualizada"] = bool(cambiadas)
        o["cambiaron"] = cambiadas
    return guardadas


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
    # Una sola vez para todo el lote: son dos queries agrupadas, y
    # repetirlas por cuenta en paralelo seria multiplicar la carga sobre
    # movimiento_staging por el tamaño del lote.
    mc = movimientos_comparados(encargo_id)

    def _una(fila: dict) -> dict:
        return _generar_y_guardar(d, encargo_id, cliente_id, fase, fila,
                                  usuario=usuario, mc=mc)

    with ThreadPoolExecutor(max_workers=len(seleccion)) as ex:
        return list(ex.map(_una, seleccion))


