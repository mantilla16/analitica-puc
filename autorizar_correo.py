"""
Autoriza el envío de correo UNA vez, con permiso delegado.

    python autorizar_correo.py

Imprime un código, usted lo escribe en microsoft.com/devicelogin desde
cualquier navegador, inicia sesión con su cuenta y acepta. El servidor
guarda un `refresh token` y con eso renueva su acceso por sí solo: no hay
que volver a hacer esto.

Por qué este camino y no un permiso de aplicación: `Mail.Send` de
aplicación deja enviar como cualquiera del tenant y por eso exige el
consentimiento de un administrador global. El delegado solo deja enviar
como USTED, y por eso lo puede consentir usted mismo. Menos poder, menos
permisos que pedir.

Se usa el flujo de código de dispositivo porque el servidor no tiene
navegador ni URI de redirección: no hay nada que registrar en Azure más
allá de permitir los flujos de cliente público.

En el registro de la aplicación hacen falta dos cosas:

  · Autenticación -> Configuración avanzada -> "Permitir flujos de cliente
    público" = Sí
  · Permisos de API -> Microsoft Graph -> Permisos DELEGADOS -> Mail.Send

El token queda en un archivo aparte, no en el repositorio ni en la base:
es una credencial viva y se trata como tal.
"""
from __future__ import annotations

import time

import correo as CO


def main() -> int:
    for n in ("AUDITORIA_GRAPH_TENANT", "AUDITORIA_GRAPH_CLIENTE"):
        if not CO._cfg(n):
            print(f"Falta {n} en el entorno.")
            return 1

    try:
        d = CO.iniciar_dispositivo()
    except Exception as e:
        print(f"\nNo se pudo iniciar la autorizacion: {e}\n")
        print("Si dice algo de 'public client' o 'not enabled for the\n"
              "consumer', falta activar en el registro de la aplicacion:\n"
              "  Autenticacion -> Configuracion avanzada ->\n"
              "  'Permitir flujos de cliente publico' = Si")
        return 1

    print("\n" + "=" * 62)
    print(f"  1. Abra   {d['verification_uri']}")
    print(f"  2. Escriba el codigo   {d['user_code']}")
    print(f"  3. Inicie sesion con {CO._cfg('AUDITORIA_CORREO_DE') or 'su cuenta'}")
    print("     y acepte el permiso de enviar correo en su nombre.")
    print("=" * 62)
    print(f"\nEl codigo vence en {int(d.get('expires_in', 900)) // 60} minutos."
          "\nEsperando…", flush=True)

    intervalo = int(d.get("interval", 5))
    limite = time.time() + int(d.get("expires_in", 900))
    while time.time() < limite:
        time.sleep(intervalo)
        try:
            estado, datos = CO.consultar_dispositivo(d["device_code"])
        except Exception as e:
            print(f"\nFALLO: {e}")
            return 1

        if estado == "pendiente":
            print(".", end="", flush=True)
            continue
        if estado == "lento":
            intervalo += 5
            continue
        if estado == "listo":
            CO.guardar_refresh(datos["refresh_token"])
            print("\n\nAutorizado.")
            print(f"El token quedo en {CO.ruta_token()}")
            print("\nDeje en el entorno:")
            print("  AUDITORIA_CORREO_MODO=GRAPH_USUARIO")
            print("\nY pruebe:")
            print("  .venv/bin/python probar_correo.py su-correo@rbcol.co")
            return 0

        print(f"\n\nRECHAZADO: {datos.get('error')} — "
              f"{datos.get('error_description', '')[:300]}")
        return 1

    print("\n\nSe agoto el tiempo sin que nadie aprobara el codigo.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
