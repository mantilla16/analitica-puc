import { useCallback, useEffect, useState } from "react";
import { api, fecha } from "../api";
import { Avatar, Aviso, Boton, Chip, Modal } from "../comp/Piezas";

const CAMPO = "w-full px-3 py-2 text-sm";
const VACIO = { correo: "", nombre: "", rol: "AUDITOR" };

/** Administración de usuarios. Solo la ve un ADMIN; el backend lo vuelve
 *  a exigir en cada ruta, porque ocultar un botón no es un control. */
export default function Usuarios({ yo, onVolver }) {
  const [lista, setLista] = useState([]);
  const [creando, setCreando] = useState(false);
  const [form, setForm] = useState(VACIO);
  const [error, setError] = useState(null);
  const [aviso, setAviso] = useState(null);

  const refrescar = useCallback(() => {
    api.usuarios().then(setLista).catch((e) => setError(e.message));
  }, []);

  useEffect(() => { refrescar(); }, [refrescar]);

  async function accion(fn, mensaje) {
    setError(null); setAviso(null);
    try {
      await fn();
      if (mensaje) setAviso(mensaje);
      refrescar();
    } catch (err) { setError(err.detalle ?? err.message); }
  }

  const crear = (e) => {
    e.preventDefault();
    accion(async () => {
      await api.crearUsuario({ ...form, correo: form.correo || null });
      setForm(VACIO); setCreando(false);
    }, `Usuario ${form.usuario} creado.`);
  };

  const campo = (k) => ({
    value: form[k],
    onChange: (e) => setForm({ ...form, [k]: e.target.value }),
    className: `${CAMPO} mt-1.5`,
  });

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <button onClick={onVolver} className="rotulo mb-8 hover:text-tinta">
        ← Encargos
      </button>

      <header className="mb-8 border-b border-regla pb-6">
        <p className="rotulo">Administración</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Usuarios</h1>
        <p className="mt-2 max-w-2xl text-sm text-tinta-media">
          Cada auditor entra con su propia cuenta. Lo que carga, aprueba o
          ajusta queda firmado con su nombre.
        </p>
      </header>

      {error && <div className="mb-6"><Aviso tono="error">{String(error)}</Aviso></div>}
      {aviso && <div className="mb-6"><Aviso tono="ok">{aviso}</Aviso></div>}

      {creando ? (
        <form onSubmit={crear} className="panel max-w-lg p-6">
          <p className="rotulo mb-5">Nuevo usuario</p>

          {/* No hay contrasena que asignar: la persona entra con su correo
              del dominio y un codigo. Dar de alta aqui sirve para dejarle
              el rol puesto de entrada -- que entre siendo admin, por
              ejemplo -- o el nombre ya escrito. */}
          <p className="mb-5 text-xs leading-relaxed text-tinta-suave">
            No hace falta crear las cuentas: cualquiera con un correo del
            dominio entra y se registra solo. Dé de alta a alguien aquí
            únicamente para dejarle el rol de administrador puesto antes de
            su primer ingreso.
          </p>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <label className="block">
                <span className="rotulo">Correo</span>
                <input type="email" {...campo("correo")} required
                       autoComplete="off"
                       className={`cifra ${CAMPO} mt-1.5`} />
              </label>
              <label className="block">
                <span className="rotulo">Rol</span>
                <select {...campo("rol")}>
                  <option value="AUDITOR">Auditor</option>
                  <option value="ADMIN">Administrador</option>
                </select>
              </label>
            </div>
            <label className="block">
              <span className="rotulo">Nombre completo (opcional)</span>
              <input {...campo("nombre")} />
              <span className="mt-1.5 block text-xs leading-relaxed text-tinta-suave">
                Si lo deja en blanco, la persona lo escribe ella misma la
                primera vez que entre -- junto con su cargo y su tarjeta
                profesional.
              </span>
            </label>
          </div>

          <div className="mt-7 flex gap-3">
            <Boton type="submit">Crear usuario</Boton>
            <Boton type="button" variante="texto"
                   onClick={() => { setCreando(false); setForm(VACIO); }}>
              Cancelar
            </Boton>
          </div>
        </form>
      ) : (
        <>
          <div className="mb-4 flex items-center justify-between">
            <p className="rotulo">{lista.length} usuarios</p>
            <Boton onClick={() => setCreando(true)}>Nuevo usuario</Boton>
          </div>

          {/* Tarjetas y no tabla: son pocos, y así caben el avatar, el
              estado y las acciones sin apretujarse en columnas. */}
          <div className="space-y-2">
            {lista.map((u) => {
              const soyYo = u.usuario === yo.usuario;
              return (
                <div key={u.id}
                     className={`panel flex flex-wrap items-center gap-4 px-5 py-4
                                 ${u.activo ? "" : "opacity-60"}`}>
                  <Avatar nombre={u.nombre} admin={u.rol === "ADMIN"} />

                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2 font-semibold">
                      {u.nombre}
                      {soyYo && <Chip tono="cian">usted</Chip>}
                      {u.rol === "ADMIN" && <Chip tono="morado">admin</Chip>}
                      {!u.activo && <Chip tono="rojo">inactivo</Chip>}
                      {/* Probo su buzon pero no lleno sus datos. Mientras
                          este asi no puede hacer nada mas que el
                          formulario, y conviene saberlo. */}
                      {u.registrado === false && (
                        <Chip tono="ambar">registro pendiente</Chip>
                      )}
                    </p>
                    <p className="mt-0.5 text-xs text-tinta-suave">
                      <span className="cifra">{u.correo ?? "sin correo: no puede entrar"}</span>
                      {u.cargo && <> · {u.cargo}</>}
                      {u.tarjeta_profesional && <> · T.P. {u.tarjeta_profesional}</>}
                      {" · "}
                      {u.ultimo_acceso
                        ? `último acceso ${fecha(u.ultimo_acceso)}`
                        : "nunca ha entrado"}
                    </p>
                  </div>

                  <div className="flex items-center gap-1">
                    {/* Un admin no puede quitarse el rol ni desactivarse:
                        el backend lo rechaza, así que tampoco se ofrece. */}
                    {!soyYo && (
                      <>
                        <button
                          onClick={() => accion(
                            () => api.editarUsuario(u.id, {
                              rol: u.rol === "ADMIN" ? "AUDITOR" : "ADMIN" }),
                            `${u.nombre} ahora es ${u.rol === "ADMIN" ? "auditor" : "administrador"}.`)}
                          className="pestana text-xs">
                          {u.rol === "ADMIN" ? "Quitar admin" : "Hacer admin"}
                        </button>
                        <button
                          onClick={() => accion(
                            () => api.editarUsuario(u.id, { activo: !u.activo }),
                            u.activo
                              ? `${u.nombre} quedó desactivado y sus sesiones se cerraron.`
                              : `${u.nombre} quedó activo.`)}
                          className={`pestana text-xs ${u.activo ? "hover:text-rojo" : "text-verde"}`}>
                          {u.activo ? "Desactivar" : "Activar"}
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <p className="mt-5 max-w-2xl text-xs leading-relaxed text-tinta-suave">
            Los usuarios se desactivan, no se borran: los papeles de trabajo
            registran quién cargó cada archivo y quién aprobó cada
            materialidad, y ese rastro debe seguir siendo legible.
            Desactivar cierra sus sesiones abiertas de inmediato y le impide
            volver a entrar, aunque su correo siga siendo del dominio.
          </p>
        </>
      )}

    </div>
  );
}
