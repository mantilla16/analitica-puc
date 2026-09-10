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

import base64
import json
import os
import sys

import correo as CO

CODIGO_DE_PRUEBA = "000000"


def _permisos(token: str) -> list[str]:
    """Los permisos de aplicación que trae el token, del claim `roles`.

    Se decodifica sin verificar la firma a propósito: no se está confiando
    en el token para autorizar nada, se le está preguntando qué dice de sí
    mismo para poder diagnosticar. La firma la verifica Microsoft cuando lo
    recibe.
    """
    try:
        carga = token.split(".")[1]
        carga += "=" * (-len(carga) % 4)          # base64url sin relleno
        datos = json.loads(base64.urlsafe_b64decode(carga))
        # Un token de APLICACIÓN lleva sus permisos en `roles`; uno
        # DELEGADO los lleva en `scp`, separados por espacios. Mirar solo
        # uno de los dos diría "sin permisos" sobre un token que sí los tiene.
        return (list(datos.get("roles") or [])
                + str(datos.get("scp") or "").split())
    except Exception:
        return []


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

    # Se comprueba la credencial ANTES de intentar el envío. Sin esto un
    # fallo dice solo "no salió", y las dos causas tienen remedios
    # distintos y a cargo de gente distinta: el secreto lo arregla quien
    # administra Azure, el buzón remitente quien administra Exchange.
    if CO.modo() in ("GRAPH", "GRAPH_USUARIO"):
        print("\ncomprobando la credencial…")
        try:
            token = CO._token()
            print("credencial: OK — el tenant, la aplicación y el secreto sirven")
        except Exception as e:
            print(f"\nFALLO EN LA CREDENCIAL  {e}\n")
            print(PISTAS["GRAPH"])
            return 1

        # El propio token dice qué permisos le concedieron. Preguntárselo a
        # él evita el peor diagnóstico posible: "403, revise el permiso o el
        # buzón o la política", que deja al administrador tanteando tres
        # cosas a la vez. Si Mail.Send no está en el token, el permiso no
        # está consentido y no hay nada que revisar del buzón.
        roles = _permisos(token)
        print(f"permisos  : {', '.join(roles) if roles else '(ninguno)'}")
        if "Mail.Send" not in roles:
            print("\nFALTA EL PERMISO Mail.Send EN EL TOKEN.\n")
            print("El secreto y la aplicación están bien, pero nadie le ha\n"
                  "concedido el permiso, o se agregó como Delegado en vez de\n"
                  "Aplicación. En el portal:\n\n"
                  "  Entra ID -> Registros de aplicaciones -> su app\n"
                  "  -> Permisos de API\n\n"
                  "La fila de Mail.Send tiene que decir Tipo = Aplicación\n"
                  "y Estado = Concedido, con visto verde. Si dice Delegado,\n"
                  "bórrela y agréguela de nuevo eligiendo 'Permisos de\n"
                  "aplicación'. Si el Estado no está concedido, pulse\n"
                  "'Conceder consentimiento del administrador'.\n\n"
                  "Si ese botón está en gris, su cuenta no puede consentir en\n"
                  "nombre del tenant y hace falta un Administrador global.")
            return 1

    print("\nenviando…")
    try:
        via = CO.enviar_codigo(destino, CODIGO_DE_PRUEBA, 10)
    except Exception as e:
        print(f"\nFALLO AL ENVIAR  {type(e).__name__}: {e}\n")
        if CO.modo() in ("GRAPH", "GRAPH_USUARIO"):
            print("La credencial sirve, así que el problema está en el buzón\n"
                  "remitente o en los permisos sobre él, no en Azure.\n")
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
