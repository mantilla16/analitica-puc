"""
Contraseñas y tokens de sesión. Funciones puras: no tocan la base ni
saben qué es un usuario, así que se prueban sin levantar nada.

Se usa `hashlib.scrypt` de la librería estándar en vez de bcrypt/passlib
-- una dependencia menos que instalar en cada servidor, para algo que
Python ya trae y que es un algoritmo adecuado para contraseñas (lento y
costoso en memoria a propósito).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

# n=16384 con r=8 pide ~16 MB por verificación: suficiente para que
# probar contraseñas por fuerza bruta sea caro, y despreciable para un
# login ocasional.
_N, _R, _P, _LARGO = 16384, 8, 1, 32

LARGO_MINIMO_CLAVE = 8


def hash_clave(clave: str) -> str:
    """Devuelve 'scrypt$n$r$p$salt$hash'. El formato lleva sus propios
    parámetros para poder subirlos en el futuro sin invalidar los hashes
    ya guardados."""
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(clave.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=_LARGO)
    return f"scrypt${_N}${_R}${_P}${sal.hex()}${h.hex()}"


def verificar_clave(clave: str, guardado: str) -> bool:
    """Compara en tiempo constante. Nunca lanza: un hash con formato
    inesperado es simplemente una contraseña que no coincide."""
    try:
        algo, n, r, p, sal_hex, hash_hex = guardado.split("$")
        if algo != "scrypt":
            return False
        h = hashlib.scrypt(clave.encode(), salt=bytes.fromhex(sal_hex),
                           n=int(n), r=int(r), p=int(p),
                           dklen=len(hash_hex) // 2)
        return hmac.compare_digest(h.hex(), hash_hex)
    except Exception:
        return False


def nuevo_token() -> str:
    """Token de sesión que viaja en la cookie. 32 bytes de entropía."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Lo que se guarda en la base. No lleva sal ni es lento a propósito:
    el token ya es aleatorio y largo, así que no hay nada que adivinar --
    el punto es que quien lea la tabla no pueda usar las sesiones."""
    return hashlib.sha256(token.encode()).hexdigest()


def problema_con_clave(clave: str) -> str | None:
    """Validación mínima. Devuelve el problema, o None si está bien."""
    if len(clave or "") < LARGO_MINIMO_CLAVE:
        return f"La contraseña debe tener al menos {LARGO_MINIMO_CLAVE} caracteres."
    return None


# =====================================================================
# INGRESO POR CORREO DE DOMINIO
# =====================================================================

import os
import re

DOMINIO = os.getenv("AUDITORIA_DOMINIO", "rbcol.co").strip().lower()

# Forma de un correo: no pretende validar el RFC, solo descartar lo que
# claramente no es una dirección. Quien exista de verdad lo prueba el
# código que llega al buzón, que es una comprobación mucho mejor que
# cualquier expresión regular.
_CORREO = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

LARGO_CODIGO = 6
MINUTOS_VIGENCIA_CODIGO = 10
MAX_INTENTOS_CODIGO = 5
MAX_CODIGOS_POR_VENTANA = 3
MINUTOS_VENTANA_ENVIO = 15


def normalizar_correo(correo: str | None) -> str:
    """Sin espacios y en minúsculas. Es la forma en que se compara y se
    guarda: `A.Mantilla@RBCol.co` y `a.mantilla@rbcol.co` son la misma
    persona, y tratarlas como dos cuentas partiría su rastro en dos."""
    return (correo or "").strip().lower()


def problema_con_correo(correo: str) -> str | None:
    """El problema en palabras, o None si sirve para entrar.

    Que el dominio no aplique SÍ se dice: es una regla de la firma, no un
    dato sobre quién tiene cuenta. Callarlo solo haría que la persona
    reintente creyendo que el correo no llegó.
    """
    if not correo:
        return "Escriba su correo."
    if not _CORREO.match(correo):
        return "Ese no parece un correo válido."
    if not correo.endswith("@" + DOMINIO):
        return f"Solo se puede entrar con un correo @{DOMINIO}."
    return None


def nuevo_codigo() -> str:
    """Seis dígitos, con `secrets` y no con `random`.

    Un millón de combinaciones no es mucho: lo que protege el código no es
    su longitud sino que expira en minutos, que sirve una sola vez y que
    tiene tope de intentos. Aun así se genera con el generador
    criptográfico, porque de nada sirve el tope si el siguiente código se
    puede predecir del anterior.
    """
    return f"{secrets.randbelow(10 ** LARGO_CODIGO):0{LARGO_CODIGO}d}"


def hash_codigo(codigo: str) -> str:
    """El mismo scrypt de las contraseñas.

    Podría ser un sha256 y bastaría -- el código vive diez minutos, así
    que un ataque fuera de línea sobre la tabla no alcanzaría a servir de
    nada. Se usa scrypt porque ya está aquí, ya está probado, y una
    verificación de 16 MB en un ingreso ocasional no se nota.
    """
    return hash_clave(codigo)


def verificar_codigo(codigo: str, guardado: str) -> bool:
    return verificar_clave(codigo, guardado)
