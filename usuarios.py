"""
Administración de usuarios desde el servidor.

Con el ingreso por correo la gente se registra sola: escribe su correo
@rbcol.co, recibe un código y entra. Este script cubre lo que no se puede
hacer desde la web:

    python usuarios.py listar
    python usuarios.py correo <usuario> <correo>   asigna el correo de una
                                                  cuenta antigua
    python usuarios.py admin <correo>              vuelve ADMIN a alguien
    python usuarios.py codigo <correo>             genera un código y lo
                                                   imprime aquí

`correo` existe porque las cuentas creadas antes del cambio pueden no
tener correo, y sin correo no hay forma de entrar. Es lo primero que hay
que correr después de la migración.

`codigo` es la puerta de emergencia. Si el correo de la firma deja de
salir, nadie podría entrar: no hay contraseñas. Con acceso al servidor se
genera un código válido y se lee por aquí. Queda en la bitácora como
CODIGO_MANUAL, porque es un ingreso que no pasó por el buzón de nadie y
quien revise tiene que poder verlo.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import auth
import db


def listar() -> None:
    filas = db.usuarios()
    if not filas:
        print("No hay usuarios.")
        return
    print(f"{'USUARIO':<20} {'ROL':<8} {'ESTADO':<9} {'CORREO':<32} NOMBRE")
    for u in filas:
        estado = "activo" if u["activo"] else "INACTIVO"
        correo = u["correo"] or "-- SIN CORREO: no puede entrar"
        print(f"{u['usuario']:<20} {u['rol']:<8} {estado:<9} {correo:<32} {u['nombre']}")


def asignar_correo(usuario: str, correo: str) -> None:
    u = db.usuario_por_nombre(usuario)
    if not u:
        sys.exit(f"No existe el usuario {usuario}.")
    correo = auth.normalizar_correo(correo)
    problema = auth.problema_con_correo(correo)
    if problema:
        sys.exit(problema)
    otro = db.usuario_por_correo(correo)
    if otro and str(otro["id"]) != str(u["id"]):
        sys.exit(f"Ese correo ya es de {otro['usuario']}.")
    db.actualizar_usuario(u["id"], correo=correo)
    print(f"{usuario} entra ahora con {correo}.")


def hacer_admin(correo: str) -> None:
    correo = auth.normalizar_correo(correo)
    u = db.usuario_por_correo(correo)
    if not u:
        sys.exit(f"No hay cuenta con el correo {correo}. "
                 f"Que entre una vez y vuelva a correr esto.")
    db.actualizar_usuario(u["id"], rol="ADMIN")
    print(f"{u['usuario']} ({correo}) es ADMIN.")


def generar_codigo(correo: str) -> None:
    correo = auth.normalizar_correo(correo)
    problema = auth.problema_con_correo(correo)
    if problema:
        sys.exit(problema)
    codigo = auth.nuevo_codigo()
    expira = datetime.now(timezone.utc) + timedelta(
        minutes=auth.MINUTOS_VIGENCIA_CODIGO)
    db.crear_codigo(correo, auth.hash_codigo(codigo), expira, None,
                    "usuarios.py (consola del servidor)")
    db.registrar(usuario=correo, accion="CODIGO_MANUAL", entidad="usuario",
                 detalle={"via": "consola del servidor"})
    print(f"\n   {codigo}\n")
    print(f"Vence en {auth.MINUTOS_VIGENCIA_CODIGO} minutos y sirve una vez.")
    print("Queda registrado en la bitácora como CODIGO_MANUAL.")


if __name__ == "__main__":
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    resto = sys.argv[2:]
    db.abrir()
    try:
        if orden == "listar":
            listar()
        elif orden == "correo" and len(resto) == 2:
            asignar_correo(resto[0], resto[1])
        elif orden == "admin" and len(resto) == 1:
            hacer_admin(resto[0])
        elif orden == "codigo" and len(resto) == 1:
            generar_codigo(resto[0])
        else:
            print(__doc__)
    finally:
        db.cerrar()
