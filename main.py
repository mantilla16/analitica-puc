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
import correo as CO
import db
import excel as X
import servicios as S
import analisis as A
import papel as P
import papel_excel as PX
import reglas as R

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
PUBLICAS = {"/auth/estado", "/auth/codigo", "/auth/verificar"}

# Con la cuenta a medio hacer -- buzon probado, datos sin llenar -- solo
# se puede llegar a estas. No es una restriccion cosmetica: sin ella
# alguien con un correo del dominio tendria acceso completo sin haber
# dicho ni su nombre.
SIN_REGISTRO = {"/auth/yo", "/auth/registro", "/auth/logout"}

# Nombre legible de cada acción, derivado de la ruta. El registro se hace
# solo, para todo método que escriba: si mañana se agrega un endpoint que
# modifica datos, queda registrado aunque nadie se acuerde de anotarlo.
# Lo que no esté en esta tabla se guarda con su método y ruta.
ACCIONES = [
    ("POST",   r"^/auth/logout$",                     "SALIDA",               "usuario"),
    ("POST",   r"^/encargos$",                        "ENCARGO_CREADO",       "encargo"),
    ("PUT",    r"^/encargos/[^/]+/responsable$",      "ENCARGO_REASIGNADO",   "encargo"),
    ("PUT",    r"^/encargos/[^/]+$",                  "ENCARGO_EDITADO",      "encargo"),
    ("DELETE", r"^/encargos/[^/]+$",                  "ENCARGO_BORRADO",      "encargo"),
    ("POST",   r"^/encargos/[^/]+/cargas$",           "ARCHIVO_SUBIDO",       "carga"),
    ("POST",   r"^/cargas/[^/]+/mapeo$",              "MAPEO_CONFIRMADO",     "carga"),
    ("POST",   r"/insumos/[^/]+/remapear$",            "MAPEO_INVALIDADO",     "encargo"),
    ("POST",   r"^/cargas/[^/]+/procesar$",           "CARGA_PROCESADA",      "carga"),
    ("POST",   r"^/cargas/[^/]+/promover$",           "BALANCE_PROMOVIDO",    "carga"),
    ("PUT",    r"^/encargos/[^/]+/materialidades/",   "MATERIALIDAD_GUARDADA","encargo"),
    ("PUT",    r"^/encargos/[^/]+/parametros$",       "PARAMETROS_GUARDADOS", "encargo"),
    ("PUT",    r"^/encargos/[^/]+/fase/",             "FASE_CAMBIADA",        "encargo"),
    ("POST",   r"/observaciones/lote$",               "OBSERVACIONES_IA",     "cuenta"),
    ("POST",   r"/observacion/[^/]+$",                "OBSERVACION_IA",       "cuenta"),
    ("POST",   r"^/usuarios$",                        "USUARIO_CREADO",       "usuario"),
    ("PUT",    r"^/usuarios/[^/]+$",                  "USUARIO_EDITADO",      "usuario"),
    ("POST",   r"^/alertas/[^/]+/reconocer$",         "ALERTA_RECONOCIDA",    "alerta"),
    ("POST",   r"^/alertas/despachar$",               "ALERTAS_DESPACHADAS",  "alerta"),
]

_ENCARGO_EN_RUTA = re.compile(r"^/encargos/([0-9a-fA-F-]{36})")
# Hay rutas que solo nombran la carga (/cargas/{id}/procesar). Sin esto
# quedarian fuera del control de acceso por no mencionar el encargo, que
# es justo el tipo de hueco que la puerta unica existe para evitar.
_CARGA_EN_RUTA = re.compile(r"^/cargas/([0-9a-fA-F-]{36})")


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


def _sin_acceso_al_encargo(u: dict, ruta: str) -> str | None:
    """El motivo por el que esta persona no puede tocar este encargo, o
    None si puede.

    Va en la puerta unica y no endpoint por endpoint: filtrar la lista de
    encargos esconde las tarjetas, no cierra el acceso -- quien tenga el
    id lo pediria igual. Aqui se cierra para toda ruta que nombre un
    encargo o una carga, incluidas las que se escriban manana.

    Un ADMIN pasa siempre. Un encargo sin dueño lo ve solo un ADMIN.
    """
    if u["rol"] == "ADMIN":
        return None

    m = _ENCARGO_EN_RUTA.match(ruta)
    encargo_id = m.group(1) if m else None
    if not encargo_id:
        c = _CARGA_EN_RUTA.match(ruta)
        encargo_id = db.encargo_de_carga(c.group(1)) if c else None
    if not encargo_id:
        return None

    dueno = db.dueno_de_encargo(encargo_id)
    if dueno is None:
        return "Este encargo no tiene responsable asignado; pídalo a un administrador"
    if dueno != str(u["id"]):
        return "Este encargo es de otro auditor"
    return None


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

    if u["registrado_en"] is None and ruta not in SIN_REGISTRO:
        return JSONResponse(
            {"detail": "Complete su registro para continuar",
             "registro_pendiente": True}, status_code=403)

    prohibido = _sin_acceso_al_encargo(u, ruta)
    if prohibido:
        return JSONResponse({"detail": prohibido}, status_code=403)

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


class UsuarioNuevo(BaseModel):
    correo: str
    nombre: str | None = None
    rol: str = "AUDITOR"


class UsuarioCambio(BaseModel):
    nombre: str | None = None
    correo: str | None = None
    rol: str | None = None
    activo: bool | None = None


class PedirCodigo(BaseModel):
    correo: str


class VerificarCodigo(BaseModel):
    correo: str
    codigo: str


class DatosRegistro(BaseModel):
    nombre: str
    cargo: str | None = None
    tarjeta_profesional: str | None = None
    telefono: str | None = None


def _sesion_nueva(u: dict, request: Request, response: Response) -> None:
    token = auth.nuevo_token()
    expira = datetime.now(timezone.utc) + timedelta(hours=SESION_HORAS)
    db.crear_sesion(auth.hash_token(token), u["id"], expira,
                    request.headers.get("user-agent"))
    response.set_cookie(
        COOKIE, token, httponly=True, samesite="lax",
        secure=SESION_SEGURA, max_age=SESION_HORAS * 3600, path="/",
    )


def _perfil(u: dict) -> dict:
    return {"usuario": u["usuario"], "nombre": u["nombre"],
            "correo": u["correo"], "rol": u["rol"],
            "cargo": u.get("cargo"),
            "tarjeta_profesional": u.get("tarjeta_profesional"),
            "telefono": u.get("telefono"),
            "registro_pendiente": u["registrado_en"] is None}


@app.get("/auth/estado")
def auth_estado() -> dict:
    """Sin sesion. Dice el dominio con el que se entra y si el envio de
    correo esta configurado: si no lo esta, mas vale decirlo en la
    pantalla que dejar a la gente pidiendo codigos que no salen."""
    sirve, falta = CO.configurado()
    return {"dominio": auth.DOMINIO, "correo_listo": sirve,
            "correo_problema": falta, "modo_correo": CO.modo(),
            "largo_codigo": auth.LARGO_CODIGO,
            "minutos_codigo": auth.MINUTOS_VIGENCIA_CODIGO}


@app.post("/auth/codigo")
def pedir_codigo(c: PedirCodigo, request: Request) -> dict:
    """Manda el codigo al buzon.

    Responde lo mismo exista la cuenta o no. Decir "ese correo no esta
    registrado" convertiria esta pantalla en una forma de averiguar quien
    trabaja en la firma, y no hace falta: si el correo es del dominio, la
    persona tiene derecho a entrar -- la primera vez creandose la cuenta.
    """
    correo = auth.normalizar_correo(c.correo)
    problema = auth.problema_con_correo(correo)
    if problema:
        raise HTTPException(422, problema)

    desde = datetime.now(timezone.utc) - timedelta(
        minutes=auth.MINUTOS_VENTANA_ENVIO)
    if db.codigos_recientes(correo, desde) >= auth.MAX_CODIGOS_POR_VENTANA:
        db.registrar(usuario=correo, accion="CODIGO_LIMITADO",
                     entidad="usuario", exito=False, estado_http=429,
                     detalle={"motivo": "demasiadas solicitudes"},
                     ip=_ip(request), agente=request.headers.get("user-agent"))
        raise HTTPException(
            429, f"Ya se enviaron varios codigos a ese correo. Espere "
                 f"{auth.MINUTOS_VENTANA_ENVIO} minutos o use el ultimo "
                 f"que recibio.")

    codigo = auth.nuevo_codigo()
    expira = datetime.now(timezone.utc) + timedelta(
        minutes=auth.MINUTOS_VIGENCIA_CODIGO)
    fila = db.crear_codigo(correo, auth.hash_codigo(codigo), expira,
                           _ip(request), request.headers.get("user-agent"))
    try:
        via = CO.enviar_codigo(correo, codigo, auth.MINUTOS_VIGENCIA_CODIGO)
    except Exception as e:
        # El codigo ya quedo creado y no lo recibio nadie: se BORRA, no se
        # marca usado. Una fila usada sigue contando para el limite de
        # envios, y quien reintenta porque el correo esta caido quedaria
        # bloqueado quince minutos por codigos que nunca salieron de aqui.
        db.borrar_codigo(fila["id"])
        if isinstance(e, CO.CorreoNoConfigurado):
            # Incluye CorreoNoAutorizado: el mensaje ya viene en castellano
            # y dice que hacer, asi que se pasa tal cual.
            raise HTTPException(503, str(e)) from None
        # De un fallo cualquiera -- la red, Microsoft caido -- el detalle
        # tecnico va al registro, no a la cara de quien intenta entrar.
        db.registrar(usuario=correo, accion="CODIGO_FALLIDO",
                     entidad="usuario", exito=False, estado_http=502,
                     detalle={"error": str(e)[:500]}, ip=_ip(request),
                     agente=request.headers.get("user-agent"))
        raise HTTPException(
            502, "No se pudo enviar el codigo. Intentelo de nuevo en un "
                 "momento; si sigue fallando, avise al administrador."
        ) from None

    # El codigo NO entra a la bitacora. Si queda constancia del envio.
    db.registrar(usuario=correo, accion="CODIGO_ENVIADO", entidad="usuario",
                 detalle={"via": via, "vence": expira.isoformat()},
                 ip=_ip(request), agente=request.headers.get("user-agent"))
    return {"enviado": True, "minutos": auth.MINUTOS_VIGENCIA_CODIGO}


@app.post("/auth/verificar")
def verificar_codigo(c: VerificarCodigo, request: Request,
                     response: Response) -> dict:
    """Cambia el codigo por una sesion. Si es la primera vez, crea la
    cuenta a medio hacer y el frontend pide los datos.

    La cuenta se crea DESPUES de comprobar el codigo, nunca antes: asi
    nadie puebla la tabla de usuarios escribiendo correos.
    """
    correo = auth.normalizar_correo(c.correo)
    problema = auth.problema_con_correo(correo)
    if problema:
        raise HTTPException(422, problema)

    def _fallo(motivo: str, http: int = 401) -> HTTPException:
        db.registrar(usuario=correo, accion="INGRESO_FALLIDO",
                     entidad="usuario", detalle={"motivo": motivo},
                     exito=False, estado_http=http, ip=_ip(request),
                     agente=request.headers.get("user-agent"))
        return HTTPException(http, "El codigo no es correcto o ya vencio")

    fila = db.codigo_vigente(correo)
    if not fila:
        raise _fallo("sin codigo pendiente")
    if fila["expira_en"] <= datetime.now(timezone.utc):
        raise _fallo("codigo vencido")
    if fila["intentos"] >= auth.MAX_INTENTOS_CODIGO:
        db.consumir_codigo(fila["id"])
        raise _fallo("codigo agotado por intentos", 429)
    if not auth.verificar_codigo((c.codigo or "").strip(), fila["codigo_hash"]):
        quedan = auth.MAX_INTENTOS_CODIGO - db.sumar_intento(fila["id"])
        raise _fallo(f"codigo incorrecto (quedan {max(quedan, 0)} intentos)")

    db.consumir_codigo(fila["id"])

    u = db.usuario_por_correo(correo)
    if u and not u["activo"]:
        raise _fallo("cuenta desactivada", 403)
    nuevo = u is None
    if nuevo:
        u = db.crear_usuario_por_correo(correo, correo.split("@")[0])

    _sesion_nueva(u, request, response)
    db.actualizar_usuario(u["id"], ultimo_acceso=datetime.now(timezone.utc))
    db.registrar(usuario_id=u["id"], usuario=u["usuario"],
                 accion="CUENTA_CREADA" if nuevo else "INGRESO",
                 entidad="usuario", ip=_ip(request),
                 agente=request.headers.get("user-agent"))
    return _perfil(u)


@app.put("/auth/registro")
def completar_registro(d: DatosRegistro, request: Request) -> dict:
    """Los datos que la persona llena la primera vez."""
    u = _yo(request)
    nombre = (d.nombre or "").strip()
    if len(nombre.split()) < 2:
        raise HTTPException(422, "Escriba su nombre y sus apellidos.")

    campos = {
        "nombre": nombre,
        "cargo": (d.cargo or "").strip() or None,
        "tarjeta_profesional": (d.tarjeta_profesional or "").strip() or None,
        "telefono": (d.telefono or "").strip() or None,
    }
    if u["registrado_en"] is None:
        campos["registrado_en"] = datetime.now(timezone.utc)
    actualizado = db.actualizar_usuario(u["id"], **campos)
    request.state.bitacora = {"nombre": nombre, "cargo": campos["cargo"]}
    return _perfil(actualizado)


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
    return _perfil(_yo(request))


# =====================================================================
# ADMINISTRACIÓN DE USUARIOS
# =====================================================================

@app.get("/usuarios/activos")
def usuarios_activos() -> list[dict]:
    """Usuario y nombre de los auditores activos.

    Ya no alimenta ningún selector de responsable -- el responsable sale de
    la sesión -- pero se conserva para nombrar a quien firmó un papel.
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
    """Un ADMIN da de alta a alguien antes de que entre por primera vez.

    Sirve para dejarle el rol puesto -- que entre siendo ADMIN, por
    ejemplo -- o el nombre ya escrito. No hay contrasena que asignar: la
    persona entra con su correo del dominio y un codigo, y si la cuenta ya
    existe simplemente la reconoce.
    """
    _exigir_admin(request)
    correo = auth.normalizar_correo(u.correo)
    problema = auth.problema_con_correo(correo)
    if problema:
        raise HTTPException(422, problema)
    if db.usuario_por_correo(correo):
        raise HTTPException(409, f"Ya hay una cuenta con el correo {correo}")
    if u.rol not in ("ADMIN", "AUDITOR"):
        raise HTTPException(422, "Rol debe ser ADMIN o AUDITOR")

    nombre = (u.nombre or "").strip()
    fila = db.crear_usuario_por_correo(correo, correo.split("@")[0])
    campos = {"rol": u.rol}
    if nombre:
        # Con el nombre puesto por el admin la cuenta queda registrada y no
        # se le pide el formulario. Sin nombre, lo llena la persona.
        campos["nombre"] = nombre
        campos["registrado_en"] = datetime.now(timezone.utc)
    fila = db.actualizar_usuario(fila["id"], **campos)
    request.state.bitacora = {"correo": correo, "rol": u.rol,
                              "nombre": nombre or "(lo llena la persona)"}
    return _perfil(fila)


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


class EncargoNuevo(BaseModel):
    """Sin `responsable`: sale de la sesión. Aceptarlo del cuerpo sería
    ofrecer un campo que el servidor ignora, y eso engaña a quien lo
    manda."""
    nit: str
    razon_social: str
    fecha_corte: date


class ReasignarEncargo(BaseModel):
    usuario_id: str


class EncargoCambio(BaseModel):
    """Lo editable de la ficha. Todo opcional: se cambia solo lo que venga.

    `confirmar` es la respuesta del auditor a la advertencia de que mover
    las fechas deja archivos ya cargados apuntando a otro corte. Sin ella,
    ese cambio se rechaza en vez de aplicarse en silencio.
    """
    razon_social: str | None = None
    fecha_corte: date | None = None
    fecha_cierre_anterior: date | None = None
    fecha_corte_anterior: date | None = None
    estado: str | None = None
    confirmar: bool = False


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
    """El responsable es siempre quien esta en sesion.

    No se acepta del cuerpo de la peticion aunque venga: en un papel de
    trabajo el responsable es una afirmacion sobre quien hizo el trabajo,
    y una afirmacion que el cliente puede escribir a su antojo no prueba
    nada. Sale de la sesion, igual que `subido_por` y `aprobado_por`.
    """
    u = _yo(request)
    # `responsable` guarda el NOMBRE, no el usuario de acceso: es el texto
    # que sale impreso en el papel, en el Excel y en la conclusion, y un
    # papel de trabajo lo firma una persona, no una cuenta. Quien puede
    # entrar al encargo lo decide `creado_por`, que sigue siendo el id.
    request.state.bitacora = {"nit": e.nit, "razon_social": e.razon_social,
                              "fecha_corte": e.fecha_corte,
                              "responsable": u["nombre"],
                              "usuario": u["usuario"]}
    return S.abrir_encargo(e.nit, e.razon_social, e.fecha_corte,
                           responsable=u["nombre"], creado_por=str(u["id"]))


@app.get("/encargos")
def listar_encargos(request: Request) -> list[dict]:
    u = _yo(request)
    return db.encargos(str(u["id"]), todos=u["rol"] == "ADMIN")


@app.get("/encargos/{encargo_id}")
def ver_encargo(encargo_id: str) -> dict:
    enc = db.encargo(encargo_id)
    if not enc:
        raise HTTPException(404, "Encargo no existe")
    return {**enc, "materialidades": db.materialidades(encargo_id)}


@app.put("/encargos/{encargo_id}/responsable")
def reasignar_encargo(encargo_id: str, d: ReasignarEncargo,
                      request: Request) -> dict:
    """Solo un administrador puede transferir el acceso a un encargo.

    El dueño no se toma del navegador como texto libre: se valida contra una
    cuenta activa y se actualizan juntos el id que protege el acceso y el
    responsable que aparece en los papeles de trabajo.
    """
    _exigir_admin(request)
    enc = db.encargo(encargo_id)
    if not enc:
        raise HTTPException(404, "Encargo no existe")
    destino = db.usuario_por_id(d.usuario_id)
    if not destino:
        raise HTTPException(404, "El usuario elegido no existe")
    if not destino["activo"]:
        raise HTTPException(409, "No puede asignar un encargo a un usuario inactivo")

    anterior = enc.get("responsable") or "sin responsable"
    r = db.reasignar_encargo(encargo_id, str(destino["id"]), destino["nombre"])
    request.state.bitacora = {
        "razon_social": enc["razon_social"], "antes": anterior,
        "despues": destino["nombre"], "usuario": destino["usuario"],
        "destino_id": str(destino["id"]),
    }
    return {**(r or {}), "creado_por_nombre": destino["nombre"]}


@app.put("/encargos/{encargo_id}")
def editar_encargo(encargo_id: str, c: EncargoCambio, request: Request) -> dict:
    """Edita la ficha del encargo. Solo un administrador.

    Lo delicado son las fechas. Cambiar el corte mueve los dos periodos
    comparativos, pero los archivos ya subidos conservan el periodo con el
    que entraron: el papel diria "corte a 30/06" sobre un balance de mayo,
    y saldria coherente, firmable y equivocado. Por eso el cambio se
    rechaza con la lista de lo que quedaria desalineado, y solo se aplica
    si el auditor lo confirma habiendola visto.

    Cuando se confirma NO se finge que todo esta bien: cada insumo
    desalineado queda como hallazgo BLOQUEANTE, para que el papel no se
    arme como si nada hasta que se vuelvan a subir los archivos.
    """
    _exigir_admin(request)
    enc = db.encargo(encargo_id)
    if not enc:
        raise HTTPException(404, "Encargo no existe")

    if c.estado is not None and c.estado not in ("ABIERTO", "CERRADO"):
        raise HTTPException(422, "Estado debe ser ABIERTO o CERRADO")

    campos = {k: v for k, v in
              (("fecha_corte", c.fecha_corte),
               ("fecha_cierre_anterior", c.fecha_cierre_anterior),
               ("fecha_corte_anterior", c.fecha_corte_anterior),
               ("estado", c.estado))
              if v is not None and v != enc[k]}

    razon = (c.razon_social or "").strip()
    cambia_razon = bool(razon) and razon != enc["razon_social"]
    if not campos and not cambia_razon:
        return {**enc, "sin_cambios": True}

    fechas = {k: campos.get(k, enc[k]) for k in
              ("fecha_corte", "fecha_cierre_anterior", "fecha_corte_anterior")}
    if fechas["fecha_cierre_anterior"] >= fechas["fecha_corte"]:
        raise HTTPException(422, "El cierre anterior debe ser previo al corte")
    if fechas["fecha_corte_anterior"] >= fechas["fecha_corte"]:
        raise HTTPException(
            422, "El corte del año anterior debe ser previo al corte")

    # Solo se comprueba si ALGUNA fecha cambio. Un insumo que ya estuviera
    # desalineado de antes no puede bloquear un cambio de estado o de razon
    # social: seria un "no" a algo que no rompe nada.
    mueve_fechas = any(k.startswith("fecha_") for k in campos)
    malos = (R.desalineados(db.insumos_con_periodo(encargo_id), fechas)
             if mueve_fechas else [])
    if malos and not c.confirmar:
        raise HTTPException(409, {
            "problema": "Hay archivos cargados que dejarían de corresponder "
                        "a este encargo",
            "desalineados": [
                {**m, "tenia": str(m["tenia"]), "deberia": str(m["deberia"])}
                for m in malos],
        })

    if cambia_razon:
        db.actualizar_cliente(str(enc["cliente_id"]), razon)
    if campos:
        db.actualizar_encargo(encargo_id, **campos)

    for m in malos:
        db.crear_hallazgo(
            encargo_id=encargo_id, tipo="PERIODO_CAMBIADO",
            severidad="BLOQUEANTE",
            descripcion=(
                f"Se cambiaron las fechas del encargo y el archivo de "
                f"{m['tipo']} quedó con periodo al {m['tenia']}, cuando "
                f"ahora debería cerrar al {m['deberia']}. Vuelva a subirlo: "
                f"hasta entonces el papel estaría comparando periodos que no "
                f"corresponden."),
        )

    request.state.bitacora = {
        "razon_social": razon or enc["razon_social"],
        "cambios": {k: str(v) for k, v in campos.items()},
        "razon_social_cambiada": cambia_razon,
        "desalineados": [m["tipo"] for m in malos],
    }
    return {**db.encargo(encargo_id), "desalineados": [m["tipo"] for m in malos]}


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


@app.post("/encargos/{encargo_id}/insumos/{tipo}/remapear")
def remapear(encargo_id: str, tipo: str, request: Request) -> dict:
    """Olvida el mapeo guardado de este insumo, para poder rehacerlo.

    El perfil se reutiliza en silencio en cada carga, así que sin esto un
    mapeo equivocado no tenía salida desde la aplicación.
    """
    enc = db.encargo(encargo_id)
    if not enc:
        raise HTTPException(404, "El encargo no existe")
    n = db.invalidar_perfil(enc["cliente_id"], tipo)
    request.state.bitacora = {"tipo": tipo, "perfiles_invalidados": n}
    return {"ok": True, "invalidados": n,
            "mensaje": ("El mapeo quedó sin vigencia. Vuelva a subir el "
                        "archivo y el sistema le pedirá el mapeo de nuevo."
                        if n else
                        "Este insumo no tenía un mapeo guardado.")}


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
def procesar(carga_id: str, request: Request, tareas: BackgroundTasks,
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


@app.get("/cargas/{carga_id}/hallazgos")
def hallazgos_carga(carga_id: str) -> list[dict]:
    """El detalle de los hallazgos de una carga.

    La tarjeta del archivo solo alcanza a decir "con hallazgos"; esto es lo
    que hay detrás de esa etiqueta.
    """
    _carga(carga_id)          # 404 si la carga no existe
    return db.hallazgos_detalle(carga_id)


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
