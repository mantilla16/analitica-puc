"""
Envío del código de acceso por correo.

Vive aparte del resto porque es lo único del sistema que depende de
infraestructura ajena. Si mañana la firma cambia de Microsoft 365 a otra
cosa, se cambia este archivo y nada más.

Configuración, por variables de entorno (en /etc/analitica-puc.env, que
es root:root 600 -- la contraseña del buzón no puede quedar visible en
`systemctl show` ni en el historial del shell):

    AUDITORIA_CORREO_MODO      SMTP (por defecto) | RELAY | CONSOLA
    AUDITORIA_SMTP_HOST        smtp.office365.com
    AUDITORIA_SMTP_PUERTO      587
    AUDITORIA_SMTP_USUARIO     buzón que autentica
    AUDITORIA_SMTP_CLAVE       su contraseña o contraseña de aplicación
    AUDITORIA_CORREO_DE        remitente que ve la gente
    AUDITORIA_CORREO_NOMBRE    nombre del remitente

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

import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger("analitica.correo")

ASUNTO = "Su código de acceso · Analítica PUC"


class CorreoNoConfigurado(RuntimeError):
    """Falta configuración para enviar. Se distingue de un fallo de red
    porque el remedio es distinto: uno lo arregla quien administra el
    servidor, el otro se reintenta."""


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
    necesarias = ["AUDITORIA_SMTP_HOST"]
    if modo() != "RELAY":                    # RELAY no autentica
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
