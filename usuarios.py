"""
Administración de usuarios desde el servidor.

Con el ingreso por Microsoft la gente entra sola: al pulsar «Entrar con
Microsoft» y aceptar, el sistema crea su cuenta con los datos del token
(nombre y correo). Este script cubre lo que no se puede hacer desde la
web:

    python usuarios.py listar
    python usuarios.py correo <usuario> <correo>   asigna el correo de una
                                                   cuenta antigua
    python usuarios.py admin <correo>              vuelve ADMIN a alguien

`correo` existe porque las cuentas creadas antes del ingreso por Microsoft
pueden no tener correo, y sin correo Microsoft no puede identificarlas.
"""
from __future__ import annotations

import sys

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
                 f"Que entre una vez con Microsoft y vuelva a correr esto.")
    db.actualizar_usuario(u["id"], rol="ADMIN")
    print(f"{u['usuario']} ({correo}) es ADMIN.")


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
        else:
            print(__doc__)
    finally:
        db.cerrar()
