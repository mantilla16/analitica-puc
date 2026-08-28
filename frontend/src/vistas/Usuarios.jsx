import { useCallback, useEffect, useState } from "react";
import { api, fecha } from "../api";
import { Avatar, Aviso, Boton, Chip, Modal } from "../comp/Piezas";

const CAMPO = "w-full px-3 py-2 text-sm";
const VACIO = { usuario: "", nombre: "", correo: "", clave: "", rol: "AUDITOR" };

/** Administración de usuarios. Solo la ve un ADMIN; el backend lo vuelve
 *  a exigir en cada ruta, porque ocultar un botón no es un control. */
export default function Usuarios({ yo, onVolver }) {
  const [lista, setLista] = useState([]);
  const [creando, setCreando] = useState(false);
  const [form, setForm] = useState(VACIO);
  const [error, setError] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [reiniciando, setReiniciando] = useState(null);   // usuario objetivo

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

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <label className="block">
                <span className="rotulo">Usuario</span>
                <input {...campo("usuario")} required autoComplete="off"
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
              <span className="rotulo">Nombre completo</span>
              <input {...campo("nombre")} required />
            </label>
            <label className="block">
              <span className="rotulo">Correo (opcional)</span>
              <input type="email" {...campo("correo")} />
            </label>
            <label className="block">
              <span className="rotulo">Contraseña inicial</span>
              <input type="password" {...campo("clave")} required
                     autoComplete="new-password" minLength={8} />
              <span className="mt-1.5 block text-xs text-tinta-suave">
                Mínimo 8 caracteres. El usuario puede cambiarla desde su menú.
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
                    </p>
                    <p className="mt-0.5 text-xs text-tinta-suave">
                      <span className="cifra">{u.usuario}</span>
                      {u.correo && <> · {u.correo}</>}
                      {" · "}
                      {u.ultimo_acceso
                        ? `último acceso ${fecha(u.ultimo_acceso)}`
                        : "nunca ha entrado"}
                    </p>
                  </div>

                  <div className="flex items-center gap-1">
                    <button onClick={() => setReiniciando(u)}
                            className="pestana text-xs">
                      Contraseña
                    </button>
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
          </p>
        </>
      )}

      {reiniciando && (
        <ReiniciarClave
          objetivo={reiniciando}
          onCerrar={() => setReiniciando(null)}
          onListo={(msg) => { setReiniciando(null); setAviso(msg); }}
        />
      )}
    </div>
  );
}

/** Asignar contraseña a otro usuario. Reemplaza al window.prompt, que
 *  además de verse ajeno mostraba la contraseña en claro al escribirla. */
function ReiniciarClave({ objetivo, onCerrar, onListo }) {
  const [clave, setClave] = useState("");
  const [repetida, setRepetida] = useState("");
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);

  async function guardar(e) {
    e.preventDefault();
    setError(null);
    if (clave !== repetida) return setError("Las contraseñas no coinciden.");
    setOcupado(true);
    try {
      await api.reiniciarClave(objetivo.id, clave);
      onListo(`Contraseña de ${objetivo.nombre} actualizada. Sus sesiones se cerraron.`);
    } catch (err) {
      setError(err.detalle ?? err.message);
    } finally { setOcupado(false); }
  }

  return (
    <Modal rotulo="Administración" titulo="Asignar contraseña" onCerrar={onCerrar}>
      <div className="mb-5 flex items-center gap-3 rounded-[8px] bg-papel-hondo p-3">
        <Avatar nombre={objetivo.nombre} admin={objetivo.rol === "ADMIN"} tam={32} />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{objetivo.nombre}</p>
          <p className="cifra text-xs text-tinta-suave">{objetivo.usuario}</p>
        </div>
      </div>

      <form onSubmit={guardar} className="space-y-4">
        {error && <Aviso tono="error">{String(error)}</Aviso>}
        <label className="block">
          <span className="rotulo">Nueva contraseña</span>
          <input type="password" value={clave} required autoFocus minLength={8}
                 autoComplete="new-password"
                 onChange={(e) => setClave(e.target.value)}
                 className={`${CAMPO} mt-1.5`} />
          <span className="mt-1.5 block text-xs text-tinta-suave">Mínimo 8 caracteres.</span>
        </label>
        <label className="block">
          <span className="rotulo">Repetir</span>
          <input type="password" value={repetida} required
                 autoComplete="new-password"
                 onChange={(e) => setRepetida(e.target.value)}
                 className={`${CAMPO} mt-1.5`} />
        </label>

        <Aviso tono="alerta">
          Las sesiones abiertas de {objetivo.nombre} se cerrarán. Tendrá que
          entrar de nuevo con la contraseña que le entregue.
        </Aviso>

        <div className="flex gap-3 pt-1">
          <Boton type="submit" disabled={ocupado}>
            {ocupado ? "Guardando…" : "Asignar"}
          </Boton>
          <Boton type="button" variante="texto" onClick={onCerrar}>Cancelar</Boton>
        </div>
      </form>
    </Modal>
  );
}
