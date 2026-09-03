"""
Orquestación. Aquí vive lo que antes hacían las funciones de Postgres:
cotejo de recargas, alertas, promoción a core y cuadres.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import db
import excel as X
import reglas as R


# =====================================================================
# ENCARGO
# =====================================================================

def abrir_encargo(nit: str, razon_social: str, fecha_corte: date,
                  responsable: str | None = None,
                  seudonimo: str | None = None) -> dict:
    """Crea cliente y encargo, y siembra las tres materialidades vacías.

    Los valores los digita el auditor después: hay una materialidad por
    fase (planeación, ejecución, cierre) y él decide cuáles aplicar.
    """
    cli = db.cliente_por_nit(nit)
    if cli is None:
        seudo = seudonimo or (
            "CLIENTE_" + hashlib.sha256(nit.encode()).hexdigest()[:6].upper()
        )
        cli = db.crear_cliente(nit, razon_social, seudo)

    enc = db.encargo_por_corte(cli["id"], fecha_corte)
    if enc is None:
        cierre_ant, corte_ant = R.derivar_fechas_encargo(fecha_corte)
        enc = db.crear_encargo(cli["id"], fecha_corte, cierre_ant,
                               corte_ant, responsable)

    db.sembrar_materialidades(enc["id"])

    return {**enc, "razon_social": cli["razon_social"], "nit": cli["nit"],
            "materialidades": db.materialidades(enc["id"])}


# =====================================================================
# MAPEO
# =====================================================================

def sugerir_mapeo(naturaleza: str, encabezados: list[str]) -> list[dict]:
    sin = db.sinonimos(naturaleza)
    campos = {c["campo"]: c for c in db.campos_estandar(naturaleza)}
    out = []
    for e in encabezados:
        campo = sin.get(X.norm(e))
        out.append({
            "encabezado": e,
            "campo": campo,
            "etiqueta": campos[campo]["etiqueta"] if campo else None,
            "confianza": "exacta" if campo else "sin_coincidencia",
        })
    return out


def pantalla_mapeo(carga_id: str) -> dict:
    c = db.carga(carga_id)
    nat = c["naturaleza"]
    sin = set(db.sinonimos(nat))
    est = X.inspeccionar(Path(c["archivo"]), sin)

    hoja = next((h for h in est["hojas"] if h["hoja"] == est["hoja_sugerida"]), None)
    encabezados = hoja["encabezados"] if hoja else []

    return {
        "carga_id": carga_id,
        "cliente": c["razon_social"],
        "tipo": c["tipo"],
        "naturaleza": nat,
        "campos_estandar": db.campos_estandar(nat),
        "hojas": [
            {k: h[k] for k in ("hoja", "fila_encabezado", "encabezados",
                               "reconocidos", "columnas_declaradas",
                               "columnas_reales", "dimension_mal_declarada")}
            for h in est["hojas"]
        ],
        "hoja_sugerida": est["hoja_sugerida"],
        "encabezados": encabezados,
        "sugerencia": sugerir_mapeo(nat, encabezados),
        "perfil_vigente": db.perfil_vigente(c["cliente_id"], c["tipo"]),
    }


def confirmar_mapeo(carga_id: str, mapeo: dict, usuario: str | None) -> dict:
    c = db.carga(carga_id)
    campos = db.campos_estandar(c["naturaleza"])
    problemas = R.validar_mapeo(mapeo, campos)
    errores = [p for p in problemas if p["severidad"] == "ERROR"]
    if errores:
        return {"ok": False, "problemas": problemas}

    perfil = db.guardar_perfil(c["cliente_id"], c["tipo"], mapeo,
                               usuario or c["subido_por"])
    db.actualizar_carga(carga_id, perfil_id=perfil["id"])
    return {"ok": True, "perfil_id": perfil["id"],
            "avisos": [p for p in problemas if p["severidad"] == "AVISO"]}


# =====================================================================
# PROCESO: parsear -> staging -> cotejar
# =====================================================================

def procesar(carga_id: str) -> dict:
    c = db.carga(carga_id)
    if not c["perfil_id"]:
        raise ValueError("La carga no tiene perfil de mapeo confirmado")

    perfil = db.uno("SELECT mapeo FROM core.perfil_mapeo WHERE id=%s",
                    (c["perfil_id"],))["mapeo"]
    nat = c["naturaleza"]

    filas = R.marcar_huellas(
        X.parsear(Path(c["archivo"]), perfil, nat), nat
    )
    n = db.copiar_staging(carga_id, nat, filas)
    db.actualizar_carga(carga_id, filas_staging=n)

    resultado = cotejar(carga_id)

    # La promocion se hace AQUI, del lado del servidor, y no como una segunda
    # llamada del navegador. Cuando la decidia el frontend, cualquier
    # interrupcion entre las dos llamadas -- un error de red, un recargue, el
    # auditor cambiando de pestaña -- dejaba el archivo leido en staging y
    # `core.balance` vacio, sin que nada lo dijera: el papel se armaba
    # comparando contra ceros. Un balance cargado se promueve siempre.
    promocion = None
    if nat == "BALANCE":
        # Cuando el cotejo devuelve el insumo a la carga anterior, la que hay
        # que asegurar promovida es ESA, no la que se acaba de subir.
        destino = carga_id
        if resultado["resultado"] in ("ARCHIVO_IDENTICO", "SIN_FILAS_NUEVAS"):
            prev = db.carga_previa(c["cliente_id"], c["tipo"],
                                   c["periodo_ini"], c["periodo_fin"], carga_id)
            destino = str(prev["id"]) if prev else None
            if destino and db.filas_en_balance(destino):
                destino = None          # ya esta promovida: no se toca
        if destino:
            promocion = promover_balance(destino)

    return {"filas_staging": n, "promocion": promocion, **resultado}


def cotejar(carga_id: str) -> dict:
    """Compara contra la carga anterior del mismo cliente, tipo y periodo."""
    c = db.carga(carga_id)
    nat = c["naturaleza"]

    prev = db.carga_previa(c["cliente_id"], c["tipo"],
                           c["periodo_ini"], c["periodo_fin"], carga_id)

    # --- primera carga
    if prev is None:
        cot = db.crear_cotejo(
            carga_nueva=carga_id, encargo_id=c["encargo_id"],
            resultado="PRIMERA_CARGA",
            filas_nuevas=c["filas_staging"] or 0,
            mensaje="Primera carga de este insumo para el periodo.",
        )
        return {"resultado": cot["resultado"], "mensaje": cot["mensaje"],
                "cotejo_id": cot["id"]}

    # --- archivo idéntico
    # El perfil entra en la comparación porque los MISMOS bytes leídos con
    # otro mapeo no son el mismo dato. Sin esto, corregir un mapeo
    # equivocado era imposible: al volver a subir el archivo se disparaba el
    # atajo de "archivo idéntico" y el insumo quedaba apuntando de vuelta a
    # la carga vieja, con el mapeo malo, sin decir una palabra.
    mismo_archivo = prev["hash_sha256"] == c["hash_sha256"]
    mismo_mapeo = prev["perfil_id"] == c["perfil_id"]
    if mismo_archivo and mismo_mapeo:
        msg = (f"Archivo idéntico al cargado el "
               f"{prev['fecha_carga']:%d/%m/%Y}. No se procesó.")
        cot = db.crear_cotejo(
            carga_nueva=carga_id, carga_previa=prev["id"],
            encargo_id=c["encargo_id"], resultado="ARCHIVO_IDENTICO",
            mensaje=msg,
        )
        db.actualizar_carga(carga_id, estado="REEMPLAZADA")
        if c["encargo_id"]:
            # subir() ya había apuntado el checklist a esta carga nueva;
            # como no se promueve nada, se devuelve al que sí tiene el
            # balance -- si no, la pestaña Balance queda vacía.
            db.asignar_insumo(c["encargo_id"], c["tipo"], prev["id"])
        return {"resultado": "ARCHIVO_IDENTICO", "mensaje": msg,
                "cotejo_id": cot["id"]}

    # --- comparación fila a fila
    hn = db.huellas_staging(carga_id, nat)
    hp = db.huellas_staging(prev["id"], nat)
    dif = R.cotejar(hn, hp)

    if not (dif["nuevas"] or dif["modificadas"] or dif["eliminadas"]):
        msg = (f"Sin filas nuevas. El archivo difiere solo en metadatos "
               f"({len(hn)} filas, idénticas).")
        cot = db.crear_cotejo(
            carga_nueva=carga_id, carga_previa=prev["id"],
            encargo_id=c["encargo_id"], resultado="SIN_FILAS_NUEVAS",
            filas_previas=len(hp), filas_nuevas=len(hn), mensaje=msg,
        )
        db.actualizar_carga(carga_id, estado="REEMPLAZADA")
        if c["encargo_id"]:
            db.asignar_insumo(c["encargo_id"], c["tipo"], prev["id"])
        return {"resultado": "SIN_FILAS_NUEVAS", "mensaje": msg,
                "cotejo_id": cot["id"]}

    # Fecha desde la cual el periodo está auditado.
    enc = db.encargo(c["encargo_id"]) if c["encargo_id"] else None
    corte = R.inicio_periodo_auditado(enc["fecha_corte"]) if enc else None

    nuevas = db.staging_por_llaves(carga_id, nat,
                                   dif["nuevas"] + dif["modificadas"])
    previas = db.staging_por_llaves(prev["id"], nat,
                                    dif["modificadas"] + dif["eliminadas"])

    detalles, fuera, monto = [], 0, Decimal(0)

    def _fecha(f: dict) -> date | None:
        v = f.get("fecha")
        if not v:
            return None
        try:
            return datetime.strptime(v[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    def _valor(f: dict) -> dict:
        if nat == "MOVIMIENTO":
            return {"debito": f.get("debito"), "credito": f.get("credito"),
                    "descripcion": f.get("descripcion")}
        return {"saldo_inicial": f.get("saldo_inicial"), "debito": f.get("debito"),
                "credito": f.get("credito"), "saldo_final": f.get("saldo_final")}

    for cambio, llaves in (("NUEVA", dif["nuevas"]),
                           ("MODIFICADA", dif["modificadas"]),
                           ("ELIMINADA", dif["eliminadas"])):
        for k in llaves:
            f = nuevas.get(k) or previas.get(k)
            if f is None:
                continue
            fec = _fecha(f)
            # Un balance de periodo cerrado que cambia está fuera por definición.
            if mismo_archivo:
                # Mismo archivo, otro mapeo: el cliente no tocó nada. Contar
                # esto como "cambios en periodo ya auditado" sería una alarma
                # falsa, y de las peores: acusa de manipulación lo que fue una
                # corrección nuestra.
                es_fuera = False
            elif nat == "MOVIMIENTO":
                es_fuera = bool(corte and fec and fec < corte)
            else:
                es_fuera = bool(corte and c["periodo_fin"] and c["periodo_fin"] < corte)
            if es_fuera:
                fuera += 1
                monto += abs(Decimal(f.get("debito") or 0)
                             - Decimal(f.get("credito") or 0))
            detalles.append({
                "cambio": cambio, "llave": k,
                "codigo_puc": f.get("codigo_puc"), "num_doc": f.get("num_doc"),
                "fecha": fec, "fuera_periodo": es_fuera,
                "valor_antes": _valor(previas[k]) if k in previas else None,
                "valor_ahora": _valor(nuevas[k]) if k in nuevas else None,
            })

    msg = (f"{len(dif['nuevas'])} nuevas, {len(dif['modificadas'])} modificadas, "
           f"{len(dif['eliminadas'])} eliminadas. {fuera} fuera del periodo auditado.")
    if mismo_archivo:
        msg = ("Es el MISMO archivo del cliente, leído con un mapeo de columnas "
               "distinto: lo que cambió es de qué columna sale cada cifra, no "
               "los datos. " + msg)

    cot = db.crear_cotejo(
        carga_nueva=carga_id, carga_previa=prev["id"],
        encargo_id=c["encargo_id"], resultado="CON_CAMBIOS",
        filas_previas=len(hp), filas_nuevas=len(hn),
        n_nuevas=len(dif["nuevas"]), n_modificadas=len(dif["modificadas"]),
        n_eliminadas=len(dif["eliminadas"]),
        n_fuera_periodo=fuera, monto_fuera_periodo=monto, mensaje=msg,
    )
    db.insertar_cotejo_detalle(cot["id"], detalles)

    if fuera > 0:
        _alertar(c, enc, cot["id"], fuera, monto, dif, corte)

    return {"resultado": "CON_CAMBIOS", "mensaje": msg, "cotejo_id": cot["id"],
            "n_fuera_periodo": fuera}


def _alertar(c: dict, enc: dict | None, cotejo_id: int, fuera: int,
             monto: Decimal, dif: dict, corte: date | None) -> None:
    db.crear_alerta(
        cliente_id=c["cliente_id"], encargo_id=c["encargo_id"],
        cotejo_id=cotejo_id, tipo="CAMBIO_PERIODO_CERRADO", severidad="CRITICA",
        titulo=f"Registros modificados en periodo ya auditado — {c['razon_social']}",
        cuerpo=(
            f"Se detectaron {fuera} registros nuevos o modificados con fecha "
            f"anterior al {corte:%d/%m/%Y}, es decir en un periodo contable ya "
            f"cerrado.\n\n"
            f"Insumo: {c['tipo']}\nArchivo: {Path(c['archivo']).name}\n"
            f"Nuevas: {len(dif['nuevas'])} | Modificadas: {len(dif['modificadas'])} "
            f"| Eliminadas: {len(dif['eliminadas'])}\n"
            f"Monto involucrado: {monto:,.2f}\n\n"
            f"Evidencia: cotejo_id = {cotejo_id}"
        ),
        destinatario=(enc or {}).get("responsable"),
        canal="SIMULADO", estado="PENDIENTE",
    )


def despachar_alertas() -> list[dict]:
    """Envío simulado: marca ENVIADA y deja la traza."""
    pend = db.alertas("PENDIENTE")
    for a in pend:
        db.marcar_alerta(
            a["id"], estado="ENVIADA", enviada_en=datetime.now(),
            destinatario=a["destinatario"] or "auditoria@firma.com",
        )
    return [{"id": a["id"], "titulo": a["titulo"],
             "destinatario": a["destinatario"] or "auditoria@firma.com",
             "estado": "ENVIADA"} for a in pend]


# =====================================================================
# PROMOCIÓN DEL BALANCE
# =====================================================================

def promover_balance(carga_id: str) -> dict:
    """staging -> core.balance. Filtra niveles, deriva jerarquía y signo."""
    c = db.carga(carga_id)
    niveles = db.niveles_cargables()
    por_digitos = {n["digitos"]: n for n in niveles.values()}
    exc = db.excepciones_naturaleza()
    sclase = db.signo_por_clase()

    crudo = db.staging_balance(carga_id)

    # Cómo trae este archivo los saldos se COMPRUEBA, no se configura: se
    # prueban las dos hipótesis y gana la que hace cuadrar las clases en
    # cero. Un parámetro que alguien puede poner mal sería un descuadre
    # esperando ocurrir, y aquí hay una prueba objetiva disponible.
    convencion, sumas = R.convencion_signo(crudo, sclase)
    ya_con_signo = convencion == "ARCHIVO"

    filas, descartadas = [], 0

    for s in crudo:
        cod = (s["codigo_puc"] or "").strip()
        if not cod or not cod.isdigit() or not ("1" <= cod[0] <= "7"):
            descartadas += 1
            continue
        niv = por_digitos.get(len(cod))
        if niv is None:                     # Grupo y Subauxiliar no se cargan
            descartadas += 1
            continue

        signo = R.resolver_signo(cod, exc, sclase)
        sf = Decimal(s["saldo_final"] or 0)
        # Dos cifras distintas y hace falta separarlas: `saldo_natural` es la
        # COMPARABLE -- la que suma cero y con la que se calculan las
        # variaciones -- y `saldo_naturaleza` dice de qué lado está el saldo
        # frente a su naturaleza. Con la convención del catálogo coinciden;
        # con la del archivo difieren en signo para pasivo, patrimonio e
        # ingresos, y confundirlas marcaría todos los pasivos de ese cliente
        # como naturaleza invertida.
        filas.append({
            "codigo_puc": cod, "nombre_cuenta": s["nombre_cuenta"],
            "nivel": niv["nivel"], "digitos": len(cod),
            "clase": cod[0],
            "cuenta": cod[:4] if len(cod) >= 4 else None,
            "subcuenta": cod[:6] if len(cod) >= 6 else None,
            "saldo_inicial": Decimal(s["saldo_inicial"] or 0),
            "debito": Decimal(s["debito"] or 0),
            "credito": Decimal(s["credito"] or 0),
            "saldo_final": sf, "signo": signo,
            "saldo_natural": sf if ya_con_signo else sf * signo,
            "saldo_naturaleza": sf * signo,
        })

    # Un codigo repetido tumbaba el COPY completo por la llave unica de
    # core.balance: la carga quedaba sin una sola fila y el auditor solo veia
    # un 500. Se resuelve segun por que se repite, y siempre se deja dicho.
    filas, duplicados = R.consolidar_duplicados(filas)

    n = db.promover_balance(carga_id, c["cliente_id"], filas)
    db.actualizar_carga(carga_id, convencion_signo=convencion)

    cuadre = R.cuadre_por_nivel(filas, niveles)
    lineas = R.cuadre_por_linea(filas)
    hay_bloqueantes = bool(lineas) or any(q["estado"] == "DESCUADRE" for q in cuadre)
    estado = "CON_HALLAZGOS" if hay_bloqueantes else "VALIDADA"
    db.actualizar_carga(carga_id, filas_cargadas=n, estado=estado)

    TOPE = 50   # el detalle se acota para no inundar la tabla de hallazgos

    for d in duplicados[:TOPE]:
        if d["trato"] == "IDENTICA":
            que = (f"El codigo aparece {d['veces']} veces con cifras identicas: "
                   f"es la misma linea repetida en el archivo. Se conservo una "
                   f"sola; sumarlas habria doblado la cuenta.")
        else:
            que = (f"El codigo aparece {d['veces']} veces con cifras distintas "
                   f"(centros de costo, sucursales o terceros). Se sumaron en "
                   f"un solo saldo de {d['saldo_final']}.")
        db.crear_hallazgo(
            encargo_id=c["encargo_id"], carga_id=carga_id,
            tipo="CODIGO_REPETIDO", severidad="ADVERTENCIA",
            codigo_puc=d["codigo_puc"], monto=d["saldo_final"],
            descripcion=f"{d['nombre_cuenta'] or ''}. {que}".strip(),
        )
    if len(duplicados) > TOPE:
        db.crear_hallazgo(
            encargo_id=c["encargo_id"], carga_id=carga_id,
            tipo="DETALLE_TRUNCADO", severidad="INFORMATIVO",
            descripcion=(f"Hay {len(duplicados)} codigos repetidos; el detalle "
                         f"solo lista los primeros {TOPE}."),
        )

    for m in lineas[:TOPE]:
        db.crear_hallazgo(
            encargo_id=c["encargo_id"], carga_id=carga_id,
            tipo="DESCUADRE_LINEA", severidad="BLOQUEANTE",
            codigo_puc=m["codigo_puc"], monto=m["diferencia"],
            descripcion="saldo_inicial + debito - credito <> saldo_final",
            fila_origen=m["fila_origen"],
        )
    # Un tope que no se declara se lee como "esos son todos": el auditor
    # revisa 50 cuentas creyendo que agotó el problema. Se deja constancia.
    if len(lineas) > TOPE:
        db.crear_hallazgo(
            encargo_id=c["encargo_id"], carga_id=carga_id,
            tipo="DETALLE_TRUNCADO", severidad="INFORMATIVO",
            descripcion=(f"Hay {len(lineas)} cuentas descuadradas; el detalle "
                         f"solo lista las primeras {TOPE}. Las restantes "
                         f"{len(lineas) - TOPE} existen pero no se enumeran "
                         f"aquí: revise el balance completo."),
        )

    for q in cuadre:
        if q["estado"] == "DESCUADRE":
            db.crear_hallazgo(
                encargo_id=c["encargo_id"], carga_id=carga_id,
                tipo="DESCUADRE_NIVEL", severidad="BLOQUEANTE",
                monto=q["suma_saldo_final"],
                descripcion=f"El nivel {q['nivel']} no suma cero ({q['filas']} filas)",
            )

    return {"promovidas": n, "descartadas": descartadas,
            "cuadre": cuadre, "descuadres_linea": len(lineas),
            "duplicados": len(duplicados),
            "convencion_signo": convencion, "sumas_convencion": sumas}
