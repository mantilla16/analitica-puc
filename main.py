"""
API de cargables — Auditoría PUC.

La base solo tiene tablas. Toda la lógica está en reglas.py y servicios.py.

    uvicorn main:app --reload
    http://localhost:8000/docs
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import (BackgroundTasks, FastAPI, File, Form, HTTPException,
                     Request, Response, UploadFile)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import auth
import db
import excel as X
import servicios as S
import analisis as A
import papel as P
import papel_excel as PX

ALMACEN = Path("./archivos")
ALMACEN.mkdir(exist_ok=True)

COOKIE = "sesion"
SESION_HORAS = int(os.getenv("SESION_HORAS", "12"))
# Marcar la cookie como Secure impide que viaje por HTTP plano. Queda en
# 0 por defecto porque azure sirve por HTTP sin certificado y activarlo
# ahí dejaría a todo el mundo sin poder entrar. Donde haya HTTPS (el
# funnel de Tailscale, o certbot) debe ponerse en 1.
SESION_SEGURA = os.getenv("SESION_SEGURA", "0") in ("1", "true", "True", "si")

app = FastAPI(title="Auditoría PUC — Cargables", version="0.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _abrir() -> None:
    db.abrir()


@app.on_event("shutdown")
def _cerrar() -> None:
    db.cerrar()


# =====================================================================
# SESIÓN
# =====================================================================

# Lo único accesible sin sesión. Todo lo demás exige haber entrado.
PUBLICAS = {"/auth/login", "/auth/estado"}

# Nombre legible de cada acción, derivado de la ruta. El registro se hace
# solo, para todo método que escriba: si mañana se agrega un endpoint que
# modifica datos, queda registrado aunque nadie se acuerde de anotarlo.
# Lo que no esté en esta tabla se guarda con su método y ruta.
ACCIONES = [
    ("POST",   r"^/auth/logout$",                     "SALIDA",               "usuario"),
    ("POST",   r"^/encargos$",                        "ENCARGO_CREADO",       "encargo"),
    ("DELETE", r"^/encargos/[^/]+$",                  "ENCARGO_BORRADO",      "encargo"),
    ("POST",   r"^/encargos/[^/]+/cargas$",           "ARCHIVO_SUBIDO",       "carga"),
    ("POST",   r"^/cargas/[^/]+/mapeo$",              "MAPEO_CONFIRMADO",     "carga"),
    ("POST",   r"^/cargas/[^/]+/procesar$",           "CARGA_PROCESADA",      "carga"),
    ("POST",   r"^/cargas/[^/]+/promover$",           "BALANCE_PROMOVIDO",    "carga"),
    ("PUT",    r"^/encargos/[^/]+/materialidades/",   "MATERIALIDAD_GUARDADA","encargo"),
    ("PUT",    r"^/encargos/[^/]+/parametros$",       "PARAMETROS_GUARDADOS", "encargo"),
    ("PUT",    r"^/encargos/[^/]+/fase/",             "FASE_CAMBIADA",        "encargo"),
    ("POST",   r"/observaciones/lote$",               "OBSERVACIONES_IA",     "cuenta"),
    ("POST",   r"/observacion/[^/]+$",                "OBSERVACION_IA",       "cuenta"),
    ("POST",   r"^/usuarios$",                        "USUARIO_CREADO",       "usuario"),
    ("PUT",    r"^/usuarios/[^/]+/clave$",            "CLAVE_REINICIADA",     "usuario"),
    ("PUT",    r"^/usuarios/[^/]+$",                  "USUARIO_EDITADO",      "usuario"),
    ("PUT",    r"^/auth/clave$",                      "CLAVE_CAMBIADA",       "usuario"),
    ("POST",   r"^/alertas/[^/]+/reconocer$",         "ALERTA_RECONOCIDA",    "alerta"),
    ("POST",   r"^/alertas/despachar$",               "ALERTAS_DESPACHADAS",  "alerta"),
]

_ENCARGO_EN_RUTA = re.compile(r"^/encargos/([0-9a-fA-F-]{36})")


def _accion_de(metodo: str, ruta: str) -> tuple[str, str | None]:
    for m, patron, accion, entidad in ACCIONES:
        if m == metodo and re.search(patron, ruta):
            return accion, entidad
    return f"{metodo} {ruta}", None


def _ip(request: Request) -> str | None:
    """Detrás de nginx la dirección directa siempre sería 127.0.0.1; la
    real viene en las cabeceras que nginx agrega."""
    return (request.headers.get("x-real-ip")
            or (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
            or (request.client.host if request.client else None))


@app.middleware("http")
async def exigir_sesion(request: Request, call_next):
    """Puerta única: en vez de proteger ruta por ruta -- donde olvidar un
    decorador deja un hueco silencioso -- se exige sesión para todo y se
    listan las excepciones. De paso deja el rastro de toda escritura."""
    ruta = request.url.path
    if request.method == "OPTIONS" or ruta in PUBLICAS:
        return await call_next(request)

    token = request.cookies.get(COOKIE)
    u = db.usuario_de_sesion(auth.hash_token(token)) if token else None
    if not u:
        return JSONResponse({"detail": "No autenticado"}, status_code=401)

    request.state.usuario = u
    respuesta = await call_next(request)

    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        accion, entidad = _accion_de(request.method, ruta)
        enc = _ENCARGO_EN_RUTA.match(ruta)
        try:
            db.registrar(
                usuario_id=u["id"], usuario=u["usuario"],
                accion=accion, entidad=entidad,
                entidad_id=ruta.rstrip("/").rsplit("/", 1)[-1],
                encargo_id=enc.group(1) if enc else None,
                # Los endpoints enriquecen el registro dejando contexto en
                # request.state; el registro base existe igual sin eso.
                detalle=getattr(request.state, "bitacora", None),
                exito=respuesta.status_code < 400,
                estado_http=respuesta.status_code,
                ip=_ip(request), agente=request.headers.get("user-agent"),
            )
        except Exception:
            # El rastro no puede tumbar la operación que estaba
            # registrando: se pierde la entrada, no el trabajo del auditor.
            pass

    return respuesta


def _yo(request: Request) -> dict:
    return request.state.usuario


def _quien(request: Request) -> str:
    """Con quién se firma lo que se guarda. Sale de la sesión, no de un
    parámetro que el cliente pueda escribir a su antojo."""
    return _yo(request)["usuario"]


def _exigir_admin(request: Request) -> dict:
    u = _yo(request)
    if u["rol"] != "ADMIN":
        raise HTTPException(403, "Requiere rol ADMIN")
    return u


class Credenciales(BaseModel):
    usuario: str
    clave: str


class UsuarioNuevo(BaseModel):
    usuario: str
    nombre: str
    correo: str | None = None
    clave: str
    rol: str = "AUDITOR"


class UsuarioCambio(BaseModel):
    nombre: str | None = None
    correo: str | None = None
    rol: str | None = None
    activo: bool | None = None


class ClaveNueva(BaseModel):
    clave: str
    clave_actual: str | None = None


@app.get("/auth/estado")
def auth_estado() -> dict:
    """Sin sesión: sirve para que el frontend distinga 'no hay usuarios
    todavía' de 'no has entrado'."""
    return {"hay_usuarios": db.hay_usuarios()}


@app.post("/auth/login")
def login(c: Credenciales, request: Request, response: Response) -> dict:
    u = db.usuario_por_nombre(c.usuario)
    # Mismo mensaje para usuario inexistente, contraseña mala o cuenta
    # desactivada: decir cuál de los tres falló ayuda a quien tantea.
    if not u or not u["activo"] or not auth.verificar_clave(c.clave, u["clave_hash"]):
        # El intento fallido sí se guarda con el motivo real: es la señal
        # de que alguien está probando, y quien revisa la bitácora
        # necesita distinguir un olvido de contraseña de un tanteo.
        motivo = ("usuario inexistente" if not u
                  else "cuenta desactivada" if not u["activo"]
                  else "contraseña incorrecta")
        db.registrar(usuario_id=u["id"] if u else None, usuario=c.usuario,
                     accion="INGRESO_FALLIDO", entidad="usuario",
                     detalle={"motivo": motivo}, exito=False, estado_http=401,
                     ip=_ip(request), agente=request.headers.get("user-agent"))
        raise HTTPException(401, "Usuario o contraseña incorrectos")

    token = auth.nuevo_token()
    expira = datetime.now(timezone.utc) + timedelta(hours=SESION_HORAS)
    db.crear_sesion(auth.hash_token(token), u["id"], expira,
                    request.headers.get("user-agent"))

    response.set_cookie(
        COOKIE, token, httponly=True, samesite="lax",
        secure=SESION_SEGURA, max_age=SESION_HORAS * 3600, path="/",
    )
    db.registrar(usuario_id=u["id"], usuario=u["usuario"], accion="INGRESO",
                 entidad="usuario", ip=_ip(request),
                 agente=request.headers.get("user-agent"))
    return {"usuario": u["usuario"], "nombre": u["nombre"], "rol": u["rol"]}


@app.post("/auth/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(COOKIE)
    if token:
        db.borrar_sesion(auth.hash_token(token))
    response.delete_cookie(COOKIE, path="/")
    request.state.bitacora = {"motivo": "salida voluntaria"}
    return {"ok": True}


@app.get("/auth/yo")
def yo(request: Request) -> dict:
    u = _yo(request)
    return {"usuario": u["usuario"], "nombre": u["nombre"], "rol": u["rol"]}


@app.put("/auth/clave")
def cambiar_mi_clave(c: ClaveNueva, request: Request) -> dict:
    """Cambio de la propia contraseña. Exige la actual: si alguien deja
    la sesión abierta, no puede quedarse con la cuenta."""
    u = db.usuario_por_nombre(_quien(request))
    if not auth.verificar_clave(c.clave_actual or "", u["clave_hash"]):
        raise HTTPException(403, "La contraseña actual no coincide")
    problema = auth.problema_con_clave(c.clave)
    if problema:
        raise HTTPException(422, problema)
    db.actualizar_usuario(u["id"], clave_hash=auth.hash_clave(c.clave))
    return {"ok": True}


# =====================================================================
# ADMINISTRACIÓN DE USUARIOS
# =====================================================================

@app.get("/usuarios/activos")
def usuarios_activos() -> list[dict]:
    """Usuario y nombre de quienes pueden ser responsables de un encargo.
    Disponible para cualquier sesión: no expone rol, correo ni estado."""
    return db.usuarios_activos()


@app.get("/usuarios")
def listar_usuarios(request: Request) -> list[dict]:
    _exigir_admin(request)
    return db.usuarios()


# =====================================================================
# BITÁCORA
# =====================================================================

@app.get("/bitacora")
def ver_bitacora(request: Request, usuario: str | None = None,
                 accion: str | None = None, encargo_id: str | None = None,
                 desde: date | None = None, hasta: date | None = None,
                 limite: int = 200, desplazamiento: int = 0) -> dict:
    """Rastro de uso. Solo para ADMIN: dice quién hizo qué y desde dónde,
    y eso no es información que deba circular entre todo el equipo."""
    _exigir_admin(request)
    return {
        "filas": db.bitacora(usuario, accion, encargo_id, desde, hasta,
                             min(limite, 500), desplazamiento),
        "acciones": db.acciones_registradas(),
    }


@app.post("/usuarios")
def crear_usuario(u: UsuarioNuevo, request: Request) -> dict:
    _exigir_admin(request)
    problema = auth.problema_con_clave(u.clave)
    if problema:
        raise HTTPException(422, problema)
    if db.usuario_por_nombre(u.usuario):
        raise HTTPException(409, f"El usuario {u.usuario} ya existe")
    if u.rol not in ("ADMIN", "AUDITOR"):
        raise HTTPException(422, "Rol debe ser ADMIN o AUDITOR")
    request.state.bitacora = {"usuario": u.usuario, "nombre": u.nombre,
                              "rol": u.rol}
    return db.crear_usuario(u.usuario, u.nombre, u.correo,
                            auth.hash_clave(u.clave), u.rol)


@app.put("/usuarios/{usuario_id}")
def editar_usuario(usuario_id: str, c: UsuarioCambio, request: Request) -> dict:
    yo_ = _exigir_admin(request)
    objetivo = db.usuario_por_id(usuario_id)
    if not objetivo:
        raise HTTPException(404, "Usuario no existe")

    campos = {k: v for k, v in c.model_dump().items() if v is not None}
    if campos.get("rol") not in (None, "ADMIN", "AUDITOR"):
        raise HTTPException(422, "Rol debe ser ADMIN o AUDITOR")

    # Nadie puede dejarse a sí mismo sin acceso ni quitarse el rol: sin
    # esto, un solo clic desafortunado deja el sistema sin ningún admin y
    # sin forma de entrar por la web a arreglarlo.
    if str(objetivo["id"]) == str(yo_["id"]):
        if campos.get("activo") is False:
            raise HTTPException(409, "No puede desactivar su propia cuenta")
        if campos.get("rol") == "AUDITOR":
            raise HTTPException(409, "No puede quitarse a sí mismo el rol ADMIN")

    request.state.bitacora = {"objetivo": objetivo["usuario"], "cambios": campos}
    r = db.actualizar_usuario(usuario_id, **campos)
    if campos.get("activo") is False:
        db.borrar_sesiones_de(usuario_id)
    return r


@app.put("/usuarios/{usuario_id}/clave")
def reiniciar_clave(usuario_id: str, c: ClaveNueva, request: Request) -> dict:
    """Un admin asigna contraseña nueva a otro usuario, sin conocer la
    anterior. Cierra las sesiones de esa cuenta."""
    _exigir_admin(request)
    objetivo = db.usuario_por_id(usuario_id)
    if not objetivo:
        raise HTTPException(404, "Usuario no existe")
    request.state.bitacora = {"objetivo": objetivo["usuario"]}
    problema = auth.problema_con_clave(c.clave)
    if problema:
        raise HTTPException(422, problema)
    db.actualizar_usuario(usuario_id, clave_hash=auth.hash_clave(c.clave))
    db.borrar_sesiones_de(usuario_id)
    return {"ok": True}


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
    aplica_variacion: bool = True
    aplica_trivialidad: bool = True


class LoteObservaciones(BaseModel):
    codigos: list[str]


class AjusteObservacion(BaseModel):
    instruccion: str | None = None


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
def abrir_encargo(e: EncargoNuevo, request: Request) -> dict:
    request.state.bitacora = {"nit": e.nit, "razon_social": e.razon_social,
                              "fecha_corte": e.fecha_corte,
                              "responsable": e.responsable}
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
def eliminar_encargo(encargo_id: str, request: Request) -> dict:
    """Borra el encargo. Las cargas ya subidas (y su balance promovido)
    no se tocan -- son del cliente, no del encargo -- así que la próxima
    vez que se abra un encargo nuevo para el mismo NIT, sigue pudiendo
    reutilizarlas si aplica."""
    enc = db.encargo(encargo_id)
    if not enc:
        raise HTTPException(404, "Encargo no existe")
    # Se anota antes de borrar: después ya no hay a quién preguntarle.
    request.state.bitacora = {"razon_social": enc["razon_social"],
                              "nit": enc["nit"], "fecha_corte": enc["fecha_corte"]}
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
                         request: Request) -> dict:
    request.state.bitacora = {"fase": fase, "valor": m.valor,
                              "porcentaje": m.porcentaje, "aplicar": m.aplicar}
    fila = db.guardar_materialidad(encargo_id, fase, m.valor, m.porcentaje,
                                   m.aplicar, m.nombre, _quien(request))
    if not fila:
        raise HTTPException(404, f"No existe materialidad de fase {fase}")
    return fila


@app.put("/encargos/{encargo_id}/fase/{fase}")
def fijar_fase(encargo_id: str, fase: str) -> dict:
    db.fijar_fase(encargo_id, fase)
    return {"fase_activa": fase}


@app.put("/encargos/{encargo_id}/parametros")
def guardar_parametros(encargo_id: str, p: Parametros, request: Request) -> dict:
    request.state.bitacora = p.model_dump()
    db.guardar_parametros(encargo_id, p.pct_variacion, p.pct_trivialidad,
                          p.aplica_variacion, p.aplica_trivialidad)
    return db.parametros(encargo_id)


# -------------------------------------------------------------------- cargas

@app.post("/encargos/{encargo_id}/cargas")
async def subir(
    encargo_id: str,
    tipo: str = Form(...),
    archivo: UploadFile = File(...),
    periodo_ini: date | None = Form(None),
    periodo_fin: date | None = Form(None),
    request: Request = None,
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
                           perfil["id"] if perfil else None, _quien(request))
        db.asignar_insumo(encargo_id, tipo, c["id"])

        request.state.bitacora = {
            "tipo": tipo, "archivo": archivo.filename, "hash": hash_,
            "periodo": f"{periodo_ini} a {periodo_fin}",
            "requiere_mapeo": perfil is None,
        }
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
                    request: Request) -> dict:
    _carga(carga_id)
    mapeo = {
        "hoja": m.hoja,
        "columnas": {k: v for k, v in m.columnas.items() if v},
        "formato_fecha": m.formato_fecha,
        "ignorar_hojas": m.ignorar_hojas,
    }
    r = S.confirmar_mapeo(carga_id, mapeo, _quien(request))
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
        r = S.procesar(carga_id)
        request.state.bitacora = {
            "tipo": c["tipo"], "resultado": r.get("resultado"),
            "filas_staging": r.get("filas_staging"),
            "fuera_periodo": r.get("n_fuera_periodo"),
        }
        return r

    tareas.add_task(_tarea, carga_id)   # movimientos: ~40 s
    return {"carga_id": carga_id, "estado": "PROCESANDO"}


@app.post("/cargas/{carga_id}/promover")
def promover(carga_id: str, request: Request) -> dict:
    c = _carga(carga_id)
    if c["naturaleza"] != "BALANCE":
        raise HTTPException(400, "Por ahora solo se promueven balances")
    r = S.promover_balance(carga_id)
    request.state.bitacora = {
        "tipo": c["tipo"], "archivo": Path(c["archivo"]).name,
        "promovidas": r["promovidas"], "descartadas": r["descartadas"],
        "descuadres_linea": r["descuadres_linea"],
        "cuadre": {q["nivel"]: q["estado"] for q in r["cuadre"]},
    }
    return r


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


@app.get("/ia/config")
def ia_config() -> dict:
    """Proveedor y modelo activos, y de cuántas en cuántas conviene pedir
    las observaciones en ESTE servidor -- no es lo mismo un endpoint en la
    nube que 12 núcleos de CPU."""
    import ia
    return ia.config()


@app.get("/encargos/{encargo_id}/papel/{fase}")
def papel_trabajo(encargo_id: str, fase: str) -> dict:
    """Papel de trabajo de revisión analítica (NIA 520): contrato de
    datos, controles, cédula comparativa, hallazgos, marcas, riesgo y
    conclusión. Puede tardar: corre el cruce contra movimientos de cada
    cuenta seleccionada."""
    return P.papel_trabajo(encargo_id, fase)


@app.get("/encargos/{encargo_id}/papel/{fase}/excel")
def papel_excel(encargo_id: str, fase: str) -> Response:
    """El mismo papel, en el formato en que se archiva y se revisa. Sale
    del mismo dict que la pantalla: si difiriera, el papel dejaría de ser
    reproducible."""
    p = P.papel_trabajo(encargo_id, fase)
    if not p.get("listo"):
        raise HTTPException(409, p.get("motivo", "No hay con qué armar el papel"))
    return Response(
        content=PX.construir(p),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":
                 f'attachment; filename="{PX.nombre_archivo(p)}"'},
    )


@app.get("/encargos/{encargo_id}/variaciones/{fase}/evidencia/{codigo}")
def evidencia_cuenta(encargo_id: str, fase: str, codigo: str) -> dict:
    """Los datos crudos detrás de una cuenta -- auxiliares, patrones,
    movimientos y el cuadre de movimientos contra la cifra -- para poder
    contrastar lo que afirma la IA."""
    return A.evidencia_cuenta(encargo_id, fase, codigo)


@app.get("/encargos/{encargo_id}/variaciones/{fase}/observaciones/guardadas")
def observaciones_guardadas(encargo_id: str, fase: str) -> list[dict]:
    """Lo que la IA ya redactó para esta fase, tal como quedó guardado.
    No llama al modelo: es lo que pinta Variaciones al abrirse."""
    return A.observaciones_guardadas(encargo_id, fase)


@app.get("/encargos/{encargo_id}/observaciones/historia")
def historia_observaciones(encargo_id: str, codigo: str | None = None) -> list[dict]:
    """Repositorio completo del cliente dueño de este encargo: todas las
    versiones que ha redactado la IA, de todos los encargos y fases."""
    return A.historia_observaciones(encargo_id, codigo)


@app.post("/encargos/{encargo_id}/variaciones/{fase}/observaciones/lote")
def observaciones_lote(encargo_id: str, fase: str, l: LoteObservaciones,
                       request: Request) -> list[dict]:
    """Varias observaciones a la vez, en paralelo -- para pedirse en
    lotes chicos (ej. 5) desde el frontend en vez de una por una o
    todas juntas en secuencia. Cada una queda guardada."""
    return A.observaciones_lote(encargo_id, fase, l.codigos, _quien(request))


@app.post("/encargos/{encargo_id}/variaciones/{fase}/observacion/{codigo}")
def observacion_cuenta(encargo_id: str, fase: str, codigo: str,
                       a: AjusteObservacion | None = None,
                       request: Request = None) -> dict:
    """Genera la observación de una cuenta y la guarda. Con `instruccion`
    reajusta la última versión según lo que indique el auditor, dejando
    una versión nueva sin borrar la anterior."""
    r = A.observacion_cuenta(encargo_id, fase, codigo,
                             a.instruccion if a else None, _quien(request))
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
def reconocer(alerta_id: int, request: Request) -> dict:
    db.marcar_alerta(alerta_id, estado="RECONOCIDA",
                     reconocida_por=_quien(request), reconocida_en=datetime.now())
    return {"alerta_id": alerta_id, "estado": "RECONOCIDA"}
