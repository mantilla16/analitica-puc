"""
Prueba el envío del código sin levantar la aplicación.

    python probar_correo.py                     usa la configuración vigente
    python probar_correo.py otro@rbcol.co       a un destinatario concreto

Existe porque configurar el correo es lo único de este sistema que depende
de un tercero, y depurarlo a través de la pantalla de ingreso es lento y
ciego: no se ve el error de Microsoft, solo un 502. Aquí sale entero.

El código que manda es fijo (000000) y no crea ninguna fila en
`core.codigo_acceso`: es una prueba de entrega, no un ingreso. No sirve
para entrar.
"""
from __future__ import annotations

import os
import sys

import correo as CO

CODIGO_DE_PRUEBA = "000000"


def main() -> int:
    destino = sys.argv[1] if len(sys.argv) > 1 else os.getenv("AUDITORIA_CORREO_DE", "")
    if not destino:
        print("Indique el destinatario: python probar_correo.py alguien@rbcol.co")
        return 1

    print(f"modo      : {CO.modo()}")
    nombre, de = CO.remitente()
    print(f"remitente : {nombre} <{de or '(sin definir)'}>")
    print(f"destino   : {destino}")

    sirve, falta = CO.configurado()
    print(f"config    : {'lista' if sirve else 'INCOMPLETA -- ' + str(falta)}")
    if not sirve:
        return 1
    if not CO.destino_permitido(destino):
        print("El modo RELAY solo entrega a correos del propio dominio.")
        return 1

    print("\nenviando…")
    try:
        via = CO.enviar_codigo(destino, CODIGO_DE_PRUEBA, 10)
    except Exception as e:
        print(f"\nFALLO  {type(e).__name__}: {e}\n")
        print(PISTAS.get(CO.modo(), ""))
        return 1

    print(f"\nOK  salió por {via}")
    print(f"Revise la bandeja de {destino}, y también correo no deseado: un")
    print("mensaje que llega pero cae en no deseado se ve igual que uno que")
    print("no llegó, y el remedio es distinto (agregar la IP al SPF).")
    return 0


PISTAS = {
    "GRAPH": """Qué revisar, en este orden:
  · "AADSTS7000215" o "invalid_client"  -> el secreto está mal o venció.
  · "AADSTS700016"                      -> el id de aplicación no existe en
                                           ese tenant.
  · 403 "Access denied" / "ErrorAccessDenied"
        -> falta consentimiento de administrador para Mail.Send, o hay una
           política de acceso de aplicación que excluye este buzón.
  · 404 "ErrorInvalidUser" / "not found"
        -> el buzón de AUDITORIA_CORREO_DE no existe o no tiene licencia de
           Exchange. Un usuario sin buzón no puede enviar.""",
    "SMTP": """Qué revisar, en este orden:
  · "535 5.7.139 Authentication unsuccessful ... basic authentication is
     disabled" -> Microsoft tiene la autenticación básica de SMTP apagada
     en el tenant o en ese buzón. Es lo más probable hoy: use GRAPH.
  · "535" a secas -> contraseña mala, o MFA activo en ese buzón.
  · tiempo de espera agotado -> el puerto 587 de salida está bloqueado.""",
    "RELAY": """Qué revisar, en este orden:
  · tiempo de espera agotado -> el puerto 25 de salida está bloqueado. Es
    frecuente: muchos proveedores lo cierran por defecto.
  · "550 5.7.64 TenantAttribution" o un rechazo de relay
        -> el tenant no acepta entrega directa (RejectDirectSend activado).
           Use GRAPH.
  · "550" por reputación -> falta la IP pública del servidor en el SPF de
    rbcol.co.""",
}


if __name__ == "__main__":
    raise SystemExit(main())
