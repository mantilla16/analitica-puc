"""
API de cargables — Auditoría PUC.

La base solo tiene tablas. Toda la lógica está en reglas.py y servicios.py.

    uvicorn main:app --reload
    http://localhost:8000/docs
"""
from __future__ import annotations

import shutil
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import db
import excel as X
import servicios as S
import analisis as A

ALMACEN = Path("./archivos")
ALMACEN.mkdir(exist_ok=True)

app = FastAPI(title="Auditoría PUC — Cargables", version="0.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _abrir() -> None:
    db.abrir()


@app.on_event("shutdown")
def _cerrar() -> None:
    db.cerrar()


class EncargoNuevo(BaseModel):
    nit: str
    razon_social: str
    fecha_corte: date
    responsable: str | None = None


class MaterialidadEntrada(BaseModel):
    valor: Decimal | None = None
    porcentaje: Decimal | None = None
    aplicar: bool = False
    nombre: str | None = None


class Parametros(BaseModel):
    pct_variacion: Decimal = Field(default=Decimal("20"), ge=0)
    pct_trivialidad: Decimal = Field(default=Decimal("5"), ge=0)


class MapeoConfirmado(BaseModel):
    hoja: str
    columnas: dict[str, str | None]
    formato_fecha: str = "DD/MM/YYYY"
    ignorar_hojas: list[str] = []


def _carga(carga_id: str) -> dict:
    c = db.carga(carga_id)
    if not c:
        raise HTTPException(404, f"Carga {carga_id} no existe")
    return c


# ------------------------------------------------------------------ encargos

@app.post("/encargos")
def abrir_encargo(e: EncargoNuevo) -> dict:
    return S.abrir_encargo(e.nit, e.razon_social, e.fecha_corte, e.responsable)


@app.get("/encargos")
def listar_encargos() -> list[dict]:
    return db.encargos()


@app.get("/encargos/{encargo_id}")
def ver_encargo(encargo_id: str) -> dict:
    enc = db.encargo(encargo_id)
    if not enc:
        raise HTTPException(404, "Encargo no existe")
    return {**enc, "materialidades": db.materialidades(encargo_id)}


@app.delete("/encargos/{encargo_id}")
def eliminar_encargo(encargo_id: str) -> dict:
    """Borra el encargo. Las cargas ya subidas (y su balance promovido)
    no se tocan -- son del cliente, no del encargo -- así que la próxima
    vez que se abra un encargo nuevo para el mismo NIT, sigue pudiendo
    reutilizarlas si aplica."""
    if not db.encargo(encargo_id):
        raise HTTPException(404, "Encargo no existe")
    db.eliminar_encargo(encargo_id)
    return {"eliminado": True}


@app.get("/encargos/{encargo_id}/checklist")
def checklist(encargo_id: str) -> list[dict]:
    return db.checklist(encargo_id)


# -------------------------------------------------------------- materialidad

@app.get("/fases")
def fases() -> list[dict]:
    return db.fases()


@app.get("/encargos/{encargo_id}/materialidades")
def materialidades(encargo_id: str) -> dict:
    return {"materialidades": db.materialidades(encargo_id),
            **db.parametros(encargo_id)}


@app.put("/encargos/{encargo_id}/materialidades/{fase}")
def guardar_materialidad(encargo_id: str, fase: str, m: MaterialidadEntrada,
                         usuario: str | None = None) -> dict:
    fila = db.guardar_materialidad(encargo_id, fase, m.valor, m.porcentaje,
                                   m.aplicar, m.nombre, usuario)
    if not fila:
        raise HTTPException(404, f"No existe materialidad de fase {fase}")
    return fila


@app.put("/encargos/{encargo_id}/fase/{fase}")
def fijar_fase(encargo_id: str, fase: str) -> dict:
    db.fijar_fase(encargo_id, fase)
    return {"fase_activa": fase}


@app.put("/encargos/{encargo_id}/parametros")
def guardar_parametros(encargo_id: str, p: Parametros) -> dict:
    db.guardar_parametros(encargo_id, p.pct_variacion, p.pct_trivialidad)
    return db.parametros(encargo_id)


# -------------------------------------------------------------------- cargas

@app.post("/encargos/{encargo_id}/cargas")
async def subir(
    encargo_id: str,
    tipo: str = Form(...),
    archivo: UploadFile = File(...),
    periodo_ini: date | None = Form(None),
    periodo_fin: date | None = Form(None),
    usuario: str | None = Form(None),
) -> dict:
    enc = db.encargo(encargo_id)
    if not enc:
        raise HTTPException(404, "Encargo no existe")
    ins = db.insumo(tipo)
    if not ins:
        raise HTTPException(400, f"Tipo de insumo desconocido: {tipo}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        shutil.copyfileobj(archivo.file, tmp)
        temporal = Path(tmp.name)

    try:
        hash_ = X.sha256_archivo(temporal)
        destino = ALMACEN / f"{hash_[:16]}_{archivo.filename}"
        if not destino.exists():
            shutil.move(str(temporal), destino)

        perfil = db.perfil_vigente(enc["cliente_id"], tipo)
        c = db.crear_carga(enc["cliente_id"], encargo_id, tipo, str(destino),
                           hash_, periodo_ini, periodo_fin,
                           perfil["id"] if perfil else None, usuario)
        db.asignar_insumo(encargo_id, tipo, c["id"])

        est = X.inspeccionar(destino, set(db.sinonimos(ins["naturaleza"])))
        return {
            "carga_id": c["id"], "tipo": tipo,
            "naturaleza": ins["naturaleza"], "hash": hash_,
            "requiere_mapeo": perfil is None,
            "perfil_id": perfil["id"] if perfil else None,
            "hojas": [
                {k: h[k] for k in ("hoja", "fila_encabezado", "encabezados",
                                   "reconocidos", "muestra")}
                for h in est["hojas"]
            ],
            "hoja_sugerida": est["hoja_sugerida"],
        }
    finally:
        if temporal.exists():
            temporal.unlink()


@app.get("/cargas/{carga_id}/mapeo")
def pantalla_mapeo(carga_id: str) -> dict:
    _carga(carga_id)
    return S.pantalla_mapeo(carga_id)


@app.post("/cargas/{carga_id}/mapeo")
def confirmar_mapeo(carga_id: str, m: MapeoConfirmado,
                    usuario: str | None = None) -> dict:
    _carga(carga_id)
    mapeo = {
        "hoja": m.hoja,
        "columnas": {k: v for k, v in m.columnas.items() if v},
        "formato_fecha": m.formato_fecha,
        "ignorar_hojas": m.ignorar_hojas,
    }
    r = S.confirmar_mapeo(carga_id, mapeo, usuario)
    if not r["ok"]:
        raise HTTPException(422, r["problemas"])
    return r


# ---------------------------------------------------------------- procesado

def _tarea(carga_id: str) -> None:
    c = db.carga(carga_id)
    try:
        S.procesar(carga_id)
    except Exception as exc:
        db.actualizar_carga(carga_id, estado="RECHAZADA")
        db.crear_hallazgo(
            encargo_id=c["encargo_id"], carga_id=carga_id,
            tipo="ERROR_PROCESO", severidad="BLOQUEANTE",
            descripcion=f"Fallo al procesar: {exc}",
        )


@app.post("/cargas/{carga_id}/procesar")
def procesar(carga_id: str, tareas: BackgroundTasks,
             sincrono: bool = False) -> dict:
    c = _carga(carga_id)
    if not c["perfil_id"]:
        raise HTTPException(409, "La carga no tiene perfil de mapeo confirmado")

    if sincrono:                        # útil para balances (820 filas)
        return S.procesar(carga_id)

    tareas.add_task(_tarea, carga_id)   # movimientos: ~40 s
    return {"carga_id": carga_id, "estado": "PROCESANDO"}


@app.post("/cargas/{carga_id}/promover")
def promover(carga_id: str) -> dict:
    c = _carga(carga_id)
    if c["naturaleza"] != "BALANCE":
        raise HTTPException(400, "Por ahora solo se promueven balances")
    return S.promover_balance(carga_id)


@app.get("/cargas/{carga_id}")
def estado_carga(carga_id: str) -> dict:
    c = _carga(carga_id)
    return {
        "carga_id": carga_id,
        "archivo": Path(c["archivo"]).name,
        "tipo": c["tipo"],
        "estado": c["estado"],
        "filas_staging": c["filas_staging"],
        "filas_cargadas": c["filas_cargadas"],
        "cotejo": db.cotejo_de_carga(carga_id),
        "hallazgos": db.hallazgos(carga_id),
    }


@app.get("/cotejos/{cotejo_id}/evidencia")
def evidencia(cotejo_id: int, solo_fuera: bool = False,
              limite: int = 200) -> list[dict]:
    return db.evidencia(cotejo_id, solo_fuera, limite)


# -------------------------------------------------------------------- análisis

@app.get("/encargos/{encargo_id}/resumen")
def resumen(encargo_id: str, tipo: str = "BAL_ACTUAL") -> list[dict]:
    """Saldo por clase, en naturaleza. Vista de entrada al balance."""
    return A.resumen_clases(encargo_id, tipo)


@app.get("/encargos/{encargo_id}/balance")
def ver_balance(encargo_id: str, tipo: str = "BAL_ACTUAL",
                nivel: str | None = None, padre: str | None = None,
                buscar: str | None = None) -> dict:
    """Filas del balance. Con `padre` devuelve sus hijos directos."""
    return A.balance(encargo_id, tipo, nivel, padre, buscar)


@app.get("/encargos/{encargo_id}/variaciones")
def variaciones(encargo_id: str, fase: str | None = None) -> dict:
    """Comparativo por cuenta con la materialidad de la fase indicada."""
    return A.variaciones(encargo_id, fase)


@app.get("/encargos/{encargo_id}/cuentas/{codigo}")
def detalle_cuenta(encargo_id: str, codigo: str) -> dict:
    """Composición de la cuenta y sus movimientos."""
    return A.detalle_cuenta(encargo_id, codigo)


@app.get("/encargos/{encargo_id}/variaciones/{fase}/observaciones")
def observaciones_ia(encargo_id: str, fase: str) -> list[dict]:
    """Una observación redactada por IA por cuenta significativa de la
    fase. Puede tardar: llama al modelo local una vez por cuenta. Sin uso
    desde el frontend hoy -- ver /observacion/{codigo}."""
    return A.observaciones(encargo_id, fase)


@app.get("/encargos/{encargo_id}/variaciones/{fase}/observaciones/lote")
def observaciones_lote(encargo_id: str, fase: str, codigos: str) -> list[dict]:
    """Varias observaciones a la vez, en paralelo -- para pedirse en
    lotes chicos (ej. 5) desde el frontend en vez de una por una o
    todas juntas en secuencia. `codigos` es una lista separada por comas."""
    lista = [c for c in codigos.split(",") if c]
    return A.observaciones_lote(encargo_id, fase, lista)


@app.get("/encargos/{encargo_id}/variaciones/{fase}/observacion/{codigo}")
def observacion_cuenta(encargo_id: str, fase: str, codigo: str) -> dict:
    """Una sola observación de IA, a pedido -- una llamada al modelo por
    clic, para no acumular varias en una petición que pueda exceder
    cualquier timeout razonable."""
    r = A.observacion_cuenta(encargo_id, fase, codigo)
    if r is None:
        raise HTTPException(404, "Cuenta no encontrada en las variaciones de esta fase")
    return r


# -------------------------------------------------------------------- alertas

@app.get("/alertas")
def alertas(estado: str | None = None) -> list[dict]:
    return db.alertas(estado)


@app.post("/alertas/despachar")
def despachar() -> list[dict]:
    return S.despachar_alertas()


@app.post("/alertas/{alerta_id}/reconocer")
def reconocer(alerta_id: int, usuario: str) -> dict:
    from datetime import datetime
    db.marcar_alerta(alerta_id, estado="RECONOCIDA",
                     reconocida_por=usuario, reconocida_en=datetime.now())
    return {"alerta_id": alerta_id, "estado": "RECONOCIDA"}
