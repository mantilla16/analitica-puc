"""
Envío del código de acceso por correo.

Vive aparte del resto porque es lo único del sistema que depende de
infraestructura ajena. Si mañana la firma cambia de Microsoft 365 a otra
cosa, se cambia este archivo y nada más.

Configuración, por variables de entorno (en /etc/analitica-puc.env, que
es root:root 600 -- la contraseña del buzón no puede quedar visible en
`systemctl show` ni en el historial del shell):

    AUDITORIA_CORREO_MODO      GRAPH_USUARIO | GRAPH | SMTP | RELAY | CONSOLA
    AUDITORIA_SMTP_HOST        smtp.office365.com
    AUDITORIA_SMTP_PUERTO      587
    AUDITORIA_SMTP_USUARIO     buzón que autentica
    AUDITORIA_SMTP_CLAVE       su contraseña o contraseña de aplicación
    AUDITORIA_CORREO_DE        remitente que ve la gente
    AUDITORIA_CORREO_NOMBRE    nombre del remitente

El modo GRAPH_USUARIO usa la API de Microsoft con permiso DELEGADO: envia
como una persona concreta, la que autorizo una vez con
`python autorizar_correo.py`. No necesita administrador global -- Mail.Send
delegado lo consiente el propio usuario -- ni contrasena guardada: lo que
queda en el servidor es un refresh token, que se puede revocar desde la
cuenta sin cambiar nada mas.

    AUDITORIA_GRAPH_TENANT     id del directorio (Entra ID)
    AUDITORIA_GRAPH_CLIENTE    id de la aplicacion
    AUDITORIA_CORREO_TOKEN     donde guardar el token (por defecto
                               ./correo_token.json)

El modo GRAPH usa la API de Microsoft con un registro de aplicacion, que es
la via soportada por Microsoft y no depende de la autenticacion basica de
SMTP, que llevan anos retirando. No hay contrasena de ninguna persona: solo
un secreto de aplicacion, que se rota sin afectar a nadie.

    AUDITORIA_GRAPH_TENANT     id del directorio (Entra ID)
    AUDITORIA_GRAPH_CLIENTE    id de la aplicacion
    AUDITORIA_GRAPH_SECRETO    secreto de la aplicacion
    AUDITORIA_CORREO_DE        buzon desde el que se envia

ADVERTENCIA: el permiso Mail.Send de aplicacion deja enviar correo COMO
CUALQUIER usuario del tenant. Hay que acotarlo con una politica de acceso de
aplicacion en Exchange Online que lo limite al buzon remitente; sin ella, ese
secreto vale para suplantar a cualquiera en la firma. Ver el README.

El modo RELAY entrega directo al servidor de la firma, sin usuario ni
contraseña. Microsoft lo permite para destinatarios del propio dominio, y
aquí TODOS lo son por definición: solo se envían códigos a @rbcol.co. Es la
opción con menos fricción porque no hay credencial que guardar ni que rotar,
y por lo tanto ninguna que se pueda filtrar. Necesita el puerto 25 de salida
abierto y conviene que la IP del servidor esté en el SPF del dominio para que
no caiga en correo no deseado.

    AUDITORIA_SMTP_HOST        rbcol-co.mail.protection.outlook.com
    AUDITORIA_SMTP_PUERTO      25

El modo CONSOLA escribe el código en el log del servicio en vez de
enviarlo, para poder probar el flujo antes de tener credenciales. NO es
el valor por defecto y no debe quedar encendido: cualquiera con acceso al
log podría entrar como cualquiera. Cuando el modo es SMTP y falta
configuración, pedir un código FALLA con un mensaje claro -- nunca se
finge que se envió algo que no salió.
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

log = logging.getLogger("analitica.correo")

ASUNTO = "Su código de acceso · Analítica PUC"


class CorreoNoConfigurado(RuntimeError):
    """Falta configuración para enviar. Se distingue de un fallo de red
    porque el remedio es distinto: uno lo arregla quien administra el
    servidor, el otro se reintenta."""


class CorreoNoAutorizado(CorreoNoConfigurado):
    """La autorización delegada dejó de servir.

    Microsoft invalida el refresh token cuando la persona cambia su
    contraseña, reconfigura su MFA o un administrador revoca sus sesiones.
    No es un fallo pasajero: no se arregla reintentando, hay que volver a
    correr `autorizar_correo.py`.

    Hereda de CorreoNoConfigurado a propósito: quien ya maneja "no se puede
    enviar" la atrapa sin cambios, y quien quiera distinguirla puede.
    """


def _cfg(nombre: str, defecto: str = "") -> str:
    return os.getenv(nombre, defecto).strip()


def modo() -> str:
    return (_cfg("AUDITORIA_CORREO_MODO", "SMTP") or "SMTP").upper()


def remitente() -> tuple[str, str]:
    de = _cfg("AUDITORIA_CORREO_DE") or _cfg("AUDITORIA_SMTP_USUARIO")
    return _cfg("AUDITORIA_CORREO_NOMBRE", "Analítica PUC"), de


def destino_permitido(correo: str) -> bool:
    """En RELAY solo se puede entregar dentro del propio dominio.

    Se comprueba aquí y no se confía en que el llamador ya lo haya hecho:
    `auth.problema_con_correo` ya exige el dominio, pero si mañana alguien
    relaja esa regla, el envío empezaría a fallar en el servidor de
    Microsoft en vez de decirlo aquí.
    """
    if modo() != "RELAY":
        return True
    import auth
    return correo.lower().endswith("@" + auth.DOMINIO)


def configurado() -> tuple[bool, str | None]:
    """(sirve, qué falta). El frontend lo usa para avisar en la pantalla
    de ingreso en vez de dejar a la gente pidiendo códigos que no salen."""
    if modo() == "CONSOLA":
        return True, None
    if modo() == "GRAPH_USUARIO":
        necesarias = ["AUDITORIA_GRAPH_TENANT", "AUDITORIA_GRAPH_CLIENTE"]
        faltan = [n for n in necesarias if not _cfg(n)]
        if faltan:
            return False, "Falta configurar " + ", ".join(faltan)
        if not _leer_refresh():
            return False, ("Nadie ha autorizado el envio todavia. En el "
                           "servidor: python autorizar_correo.py")
        revocado = _estado_token().get("revocado_en")
        if revocado:
            return False, (
                f"La autorizacion para enviar correo dejo de servir el "
                f"{revocado[:10]}. Suele pasar al cambiar la contrasena o "
                f"reconfigurar el MFA de la cuenta que autorizo. Hay que "
                f"volver a autorizarla en el servidor: "
                f"python autorizar_correo.py")
        return True, None
    if modo() == "GRAPH":
        necesarias = ["AUDITORIA_GRAPH_TENANT", "AUDITORIA_GRAPH_CLIENTE",
                      "AUDITORIA_GRAPH_SECRETO", "AUDITORIA_CORREO_DE"]
    else:
        necesarias = ["AUDITORIA_SMTP_HOST"]
        if modo() != "RELAY":                # RELAY no autentica
            necesarias += ["AUDITORIA_SMTP_USUARIO", "AUDITORIA_SMTP_CLAVE"]
    faltan = [n for n in necesarias if not _cfg(n)]
    if faltan:
        return False, "Falta configurar " + ", ".join(faltan)
    if not remitente()[1]:
        return False, "Falta configurar AUDITORIA_CORREO_DE"
    return True, None


def _cuerpo(codigo: str, minutos: int) -> tuple[str, str]:
    texto = (
        f"Su código de acceso es {codigo}\n\n"
        f"Vence en {minutos} minutos y sirve una sola vez.\n\n"
        "Si no fue usted quien lo pidió, ignore este mensaje: sin el "
        "código nadie puede entrar con su correo. Avise a la firma si "
        "le llegan códigos que no pidió.\n"
    )
    # El HTML es deliberadamente simple: un correo con imágenes, botones y
    # enlaces se parece a una suplantación, y este mensaje justamente
    # entrena a la gente a confiar en un código que le llega.
    html = f"""<!doctype html>
<html><body style="font-family:system-ui,-apple-system,Segoe UI,Arial,sans-serif;
                   background:#f6f7f9;margin:0;padding:32px">
  <div style="max-width:440px;margin:0 auto;background:#fff;border:1px solid #e4e6ea;
              border-radius:12px;padding:28px">
    <p style="margin:0;font-size:12px;letter-spacing:.08em;text-transform:uppercase;
              color:#6b7280">Analítica PUC</p>
    <p style="margin:18px 0 6px;font-size:14px;color:#374151">Su código de acceso</p>
    <p style="margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
              font-size:34px;letter-spacing:.22em;font-weight:600;color:#111827">
      {codigo}</p>
    <p style="margin:18px 0 0;font-size:13px;color:#6b7280">
      Vence en {minutos} minutos y sirve una sola vez.</p>
    <p style="margin:14px 0 0;font-size:12px;line-height:1.6;color:#9ca3af">
      Si no fue usted quien lo pidió, ignore este mensaje: sin el código
      nadie puede entrar con su correo.</p>
  </div>
</body></html>"""
    return texto, html


def enviar_codigo(correo: str, codigo: str, minutos: int) -> str:
    """Envía el código. Devuelve por dónde salió, para la bitácora.

    El código NUNCA se registra en la bitácora ni en el log (salvo en modo
    CONSOLA, que existe para eso y por eso no es el defecto): un código en
    un registro que se conserva es una contraseña escrita en la pared.
    """
    if modo() == "CONSOLA":
        log.warning("MODO CONSOLA -- codigo para %s: %s", correo, codigo)
        return "CONSOLA"

    sirve, falta = configurado()
    if not sirve:
        raise CorreoNoConfigurado(falta or "Envío de correo sin configurar")
    if not destino_permitido(correo):
        raise CorreoNoConfigurado(
            "En modo RELAY solo se entrega a correos del propio dominio")

    nombre_de, direccion_de = remitente()
    texto, html = _cuerpo(codigo, minutos)

    if modo() in ("GRAPH", "GRAPH_USUARIO"):
        return _enviar_por_graph(correo, texto, html)

    msg = EmailMessage()
    msg["Subject"] = ASUNTO
    msg["From"] = f"{nombre_de} <{direccion_de}>"
    msg["To"] = correo
    # Que un cliente de correo no ofrezca "responder a todos" sobre un
    # mensaje automático: no hay nadie leyendo esa bandeja.
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")

    relay = modo() == "RELAY"
    host = _cfg("AUDITORIA_SMTP_HOST")
    puerto = int(_cfg("AUDITORIA_SMTP_PUERTO", "25" if relay else "587") or 25)
    with smtplib.SMTP(host, puerto, timeout=30) as s:
        s.ehlo()
        if relay:
            # Sin credencial que proteger, TLS es deseable pero no
            # imprescindible: si el servidor no lo ofrece se entrega igual.
            # Lo que viaja es un codigo de un solo uso hacia el propio
            # dominio, no una contrasena.
            if s.has_extn("starttls"):
                s.starttls()
                s.ehlo()
        else:
            # STARTTLS obligatorio: sin esto la contraseña del buzón viaja
            # en claro. Si el servidor no lo ofrece, se prefiere no enviar.
            s.starttls()
            s.ehlo()
            s.login(_cfg("AUDITORIA_SMTP_USUARIO"), _cfg("AUDITORIA_SMTP_CLAVE"))
        s.send_message(msg)
    return f"{'RELAY' if relay else 'SMTP'} {host}:{puerto}"


# =====================================================================
# MICROSOFT GRAPH
# =====================================================================

_TOKEN: dict[str, object] = {}
_CANDADO = threading.Lock()

AUTORIDAD = "https://login.microsoftonline.com"
GRAPH = "https://graph.microsoft.com/v1.0"


def _pedir(url: str, datos: bytes | None, cabeceras: dict[str, str],
           timeout: int = 20) -> dict:
    req = urllib.request.Request(url, data=datos, headers=cabeceras,
                                 method="POST" if datos is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            cuerpo = r.read()
            return json.loads(cuerpo) if cuerpo else {}
    except urllib.error.HTTPError as e:
        # El detalle de Microsoft es lo unico que dice si falta el permiso,
        # si el secreto vencio o si el buzon no existe. Sin esto el auditor
        # solo veria "502" y nadie sabria por donde empezar.
        try:
            d = json.loads(e.read() or b"{}")
            msg = (d.get("error_description")
                   or (d.get("error") or {}).get("message")
                   or str(d))
        except Exception:
            msg = e.reason
        raise RuntimeError(f"Graph respondio {e.code}: {str(msg)[:300]}") from None


def _token() -> str:
    """Token de acceso, reusado hasta poco antes de vencer.

    Pedir uno por cada correo funcionaria, pero Microsoft limita la tasa de
    peticiones al endpoint de tokens: con varias personas entrando a la vez
    el limite se alcanza y los codigos dejan de salir. El candado evita que
    dos hilos pidan token simultaneamente al expirar.
    """
    with _CANDADO:
        vence = _TOKEN.get("vence")
        if vence and datetime.now(timezone.utc) < vence:
            return str(_TOKEN["valor"])

        if modo() == "GRAPH_USUARIO":
            refresh = _leer_refresh()
            if not refresh:
                raise RuntimeError(
                    "No hay autorizacion guardada. En el servidor: "
                    "python autorizar_correo.py")
            campos = {
                "client_id": _cfg("AUDITORIA_GRAPH_CLIENTE"),
                "scope": ALCANCE,
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            }
        else:
            campos = {
                "client_id": _cfg("AUDITORIA_GRAPH_CLIENTE"),
                "client_secret": _cfg("AUDITORIA_GRAPH_SECRETO"),
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            }
        try:
            r = _pedir(
                f"{AUTORIDAD}/{_cfg('AUDITORIA_GRAPH_TENANT')}/oauth2/v2.0/token",
                urllib.parse.urlencode(campos).encode(),
                {"Content-Type": "application/x-www-form-urlencoded"})
        except RuntimeError as e:
            # Se deja constancia en el archivo del token para que la
            # pantalla de ingreso pueda avisarlo ANTES de que alguien pida
            # un codigo. Sin esto, cada persona que intente entrar recibe el
            # mismo muro de texto de Microsoft y nadie sabe que hacer.
            if _revocado(str(e)):
                marcar_revocado(str(e))
                raise CorreoNoAutorizado(
                    "La autorizacion para enviar correo dejo de servir. Suele "
                    "pasar al cambiar la contrasena o reconfigurar el MFA de "
                    "la cuenta que autorizo. Hay que volver a autorizarla en "
                    "el servidor con: python autorizar_correo.py") from None
            raise
        if "access_token" not in r:
            raise RuntimeError("Graph no devolvio token")
        # Microsoft rota el refresh token en cada uso. Guardar el nuevo no
        # es opcional: si se conserva el viejo, el dia que Microsoft
        # invalide el anterior nadie podria entrar y no habria pista de por
        # que -- funcionaba hasta que dejo de funcionar.
        if r.get("refresh_token"):
            guardar_refresh(r["refresh_token"])
        # Un minuto de margen: un token que vence entre que se pide y se usa
        # produciria un 401 esporadico, del tipo que nadie logra reproducir.
        _TOKEN["valor"] = r["access_token"]
        _TOKEN["vence"] = (datetime.now(timezone.utc)
                           + timedelta(seconds=int(r.get("expires_in", 3600)) - 60))
        return str(r["access_token"])


def _olvidar_token() -> None:
    with _CANDADO:
        _TOKEN.clear()


def _enviar_por_graph(correo: str, texto: str, html: str) -> str:
    nombre_de, direccion_de = remitente()
    mensaje = {
        "message": {
            "subject": ASUNTO,
            "body": {"contentType": "HTML", "content": html},
            "toRecipients": [{"emailAddress": {"address": correo}}],
        },
        # Sin copia en Elementos enviados: son cientos de codigos al mes y
        # solo llenarian el buzon de ruido. La constancia del envio queda en
        # la bitacora, que es donde un auditor la buscaria.
        "saveToSentItems": False,
    }
    cuerpo = json.dumps(mensaje).encode("utf-8")
    # Con permiso delegado se envia como quien autorizo, y ese es el unico
    # buzon al que se tiene acceso: /me. Pedir /users/{alguien} daria 403
    # aunque ese alguien sea la misma persona.
    url = (f"{GRAPH}/me/sendMail" if modo() == "GRAPH_USUARIO"
           else f"{GRAPH}/users/{urllib.parse.quote(direccion_de)}/sendMail")

    def _mandar() -> None:
        _pedir(url, cuerpo, {"Authorization": f"Bearer {_token()}",
                             "Content-Type": "application/json"})

    try:
        _mandar()
    except RuntimeError as e:
        # Un token vive hasta una hora en memoria. Si el permiso se concede
        # DURANTE ese rato, el token cacheado sigue sin traerlo y todo
        # seguiria fallando aunque en Azure ya este bien -- el peor caso
        # para quien administra: arreglo lo que era y no cambio nada.
        # Se tira el token y se reintenta una vez.
        if "403" not in str(e):
            raise
        _olvidar_token()
        _mandar()
    return f"GRAPH {direccion_de}"


# =====================================================================
# AUTORIZACION DELEGADA (flujo de codigo de dispositivo)
# =====================================================================

# `offline_access` es lo que hace que Microsoft entregue un refresh token;
# sin el habria que volver a iniciar sesion cada hora, que es justo lo que
# un servidor no puede hacer.
ALCANCE = "offline_access https://graph.microsoft.com/Mail.Send"


def ruta_token() -> str:
    return _cfg("AUDITORIA_CORREO_TOKEN", "correo_token.json")


# Lo que dice Microsoft cuando la autorizacion ya no vale. No es un fallo
# de red ni de configuracion: es que alguien toco la cuenta.
SENALES_REVOCADO = ("AADSTS50173", "AADSTS700082", "invalid_grant")


def _revocado(mensaje: str) -> bool:
    return any(s in mensaje for s in SENALES_REVOCADO)


def _estado_token() -> dict:
    try:
        with open(ruta_token(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def marcar_revocado(motivo: str) -> None:
    """Anota que la autorizacion caduco, conservando el token.

    No se borra el refresh token: si el problema fuera otro -- una caida
    momentanea de Microsoft mal interpretada -- borrarlo obligaria a
    reautorizar sin necesidad. Se marca, y `autorizar_correo.py` limpia la
    marca cuando alguien vuelve a autorizar de verdad.
    """
    datos = _estado_token()
    datos["revocado_en"] = datetime.now(timezone.utc).isoformat()
    datos["revocado_motivo"] = motivo[:300]
    tmp = ruta_token() + ".nuevo"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, ruta_token())
    log.error("La autorizacion de correo fue revocada: %s", motivo[:300])


def _leer_refresh() -> str | None:
    try:
        with open(ruta_token(), encoding="utf-8") as f:
            return json.load(f).get("refresh_token") or None
    except (OSError, ValueError):
        return None


def guardar_refresh(token: str) -> None:
    """Guarda el refresh token con permisos restringidos.

    Se escribe en un temporal y se renombra: un reemplazo a medias dejaria
    el archivo truncado y nadie podria entrar a la aplicacion hasta volver
    a autorizar. El renombrado es atomico.
    """
    ruta = ruta_token()
    tmp = ruta + ".nuevo"
    # Sin las claves de revocacion: guardar un token nuevo ES la
    # reautorizacion, y dejar la marca haria que la pantalla siguiera
    # avisando de un problema ya resuelto.
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"refresh_token": token,
                   "guardado": datetime.now(timezone.utc).isoformat()}, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, ruta)


def iniciar_dispositivo() -> dict:
    """Pide el codigo que la persona escribe en microsoft.com/devicelogin."""
    datos = urllib.parse.urlencode({
        "client_id": _cfg("AUDITORIA_GRAPH_CLIENTE"),
        "scope": ALCANCE,
    }).encode()
    return _pedir(
        f"{AUTORIDAD}/{_cfg('AUDITORIA_GRAPH_TENANT')}/oauth2/v2.0/devicecode",
        datos, {"Content-Type": "application/x-www-form-urlencoded"})


# "Todavia no" y "pregunte mas despacio" en las formas en que Microsoft los
# dice. El campo `error` del JSON trae `authorization_pending`, pero
# `error_description` lo escribe como "Authorization is pending" junto al
# codigo AADSTS70016, y `_pedir` conserva la descripcion, no el campo. Mirar
# solo una de las dos formas hacia que la autorizacion se abortara en el
# primer sondeo, antes de que nadie alcanzara a escribir el codigo.
PENDIENTE = ("authorization_pending", "authorization is pending", "aadsts70016")


def consultar_dispositivo(device_code: str) -> tuple[str, dict]:
    """(estado, datos) mientras se espera a que la persona apruebe.

    `authorization_pending` y `slow_down` no son errores: son la forma en
    que Microsoft dice "todavia no" y "pregunte mas despacio". Tratarlos
    como fallos abortaria la autorizacion apenas empezada -- que es
    exactamente lo que pasaba, y por eso el codigo se cancelaba enseguida.
    """
    datos = urllib.parse.urlencode({
        "client_id": _cfg("AUDITORIA_GRAPH_CLIENTE"),
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "device_code": device_code,
    }).encode()
    url = f"{AUTORIDAD}/{_cfg('AUDITORIA_GRAPH_TENANT')}/oauth2/v2.0/token"
    try:
        r = _pedir(url, datos, {"Content-Type": "application/x-www-form-urlencoded"})
        return "listo", r
    except RuntimeError as e:
        # En minusculas: Microsoft alterna mayusculas entre el campo y la
        # descripcion, y una comparacion sensible a ellas volveria a fallar
        # con el mismo sintoma desconcertante.
        texto = str(e).lower()
        if any(p in texto for p in PENDIENTE):
            return "pendiente", {}
        if "slow_down" in texto:
            return "lento", {}
        return "rechazado", {"error": "", "error_description": str(e)}
