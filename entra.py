"""
Validación de id_token de Microsoft Entra ID.

El frontend obtiene un `id_token` con MSAL y lo manda aquí. Este módulo
comprueba la firma contra las claves públicas del inquilino y valida
emisor, audiencia y vigencia. Nunca se confía en el contenido del token
sin esto: un id_token sin verificar es texto que manda el navegador.

Configuración por entorno:

    AUDITORIA_MS_TENANT      id de directorio (inquilino)
    AUDITORIA_MS_CLIENTE     id de aplicación (cliente)

Los mismos valores que Autotrack — es el mismo registro en Azure, y con
eso una sola app en el portal sirve a las aplicaciones de la firma.
"""
from __future__ import annotations

import os


import jwt
from jwt import PyJWKClient


def _cfg(nombre: str) -> str:
    return os.getenv(nombre, "").strip()


def tenant() -> str:
    return _cfg("AUDITORIA_MS_TENANT")


def cliente() -> str:
    return _cfg("AUDITORIA_MS_CLIENTE")


def configurado() -> bool:
    return bool(tenant() and cliente())


# Las claves de firma de Microsoft rotan cada pocas semanas. PyJWKClient
# las cachea internamente, pero conviene tener nuestro propio TTL para
# atarlas al tenant vigente: si mañana cambia AUDITORIA_MS_TENANT, hay que
# tirar el cliente.
_CLIENTE_JWKS: PyJWKClient | None = None
_CLIENTE_JWKS_TENANT: str = ""


def _jwks_cliente() -> PyJWKClient:
    global _CLIENTE_JWKS, _CLIENTE_JWKS_TENANT
    t = tenant()
    if _CLIENTE_JWKS is None or _CLIENTE_JWKS_TENANT != t:
        url = f"https://login.microsoftonline.com/{t}/discovery/v2.0/keys"
        _CLIENTE_JWKS = PyJWKClient(url, cache_keys=True, lifespan=12 * 3600)
        _CLIENTE_JWKS_TENANT = t
    return _CLIENTE_JWKS


def verificar_id_token(id_token: str) -> dict:
    """Devuelve {correo, nombre, oid} si el token es válido para nosotros.

    Se comprueban firma, emisor, audiencia y vigencia. Ademas `tid` — el
    inquilino al que pertenece la cuenta — tiene que ser el nuestro: sin
    eso, un usuario de OTRA organización de Microsoft con el mismo correo
    podría entrar como si fuera nuestro.
    """
    if not configurado():
        raise RuntimeError("El login con Microsoft no está configurado")

    t = tenant()
    firmante = _jwks_cliente().get_signing_key_from_jwt(id_token)

    # Entra emite dos formas de emisor segun la configuracion del
    # inquilino; se aceptan las dos.
    emisores = [
        f"https://login.microsoftonline.com/{t}/v2.0",
        f"https://sts.windows.net/{t}/",
    ]

    claims = jwt.decode(
        id_token,
        firmante.key,
        algorithms=["RS256"],
        audience=cliente(),
        issuer=emisores,
        leeway=120,      # margen por desfase de reloj
    )

    if claims.get("tid") != t:
        raise ValueError("El token pertenece a otro inquilino")

    correo = (claims.get("preferred_username") or claims.get("email") or "").lower()
    if not correo:
        raise ValueError("El token no trae correo")

    return {
        "correo": correo,
        "nombre": claims.get("name") or correo,
        "oid": claims.get("oid"),
    }
