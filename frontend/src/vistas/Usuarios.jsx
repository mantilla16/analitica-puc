import { useCallback, useEffect, useState } from "react";
import { api, fecha } from "../api";
import { Aviso, Boton } from "../comp/Piezas";

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

  const refrescar = useCallback(() => {
    api.usuarios().then(setLista).catch((e) => setError(e.message));
  }, []);

  useEffect(() => { refrescar(); }, [refrescar]);

  async function crear(e) {
    e.preventDefault();
    setError(null); setAviso(null);
    try {
      await api.crearUsuario({ ...form, correo: form.correo || null });
      setForm(VACIO); setCreando(false);
      setAviso(`Usuario ${form.usuario} creado.`);
      refrescar();
    } catch (err) { setError(err.detalle ?? err.message); }
  }

  async function alternarActivo(u) {
    setError(null); setAviso(null);
    try {
      await api.editarUsuario(u.id, { activo: !u.activo });
      refrescar();
    } catch (err) { setError(err.detalle ?? err.message); }
  }

  async function cambiarRol(u) {
    setError(null); setAviso(null);
    try {
      await api.editarUsuario(u.id, { rol: u.rol === "ADMIN" ? "AUDITOR" : "ADMIN" });
      refrescar();
    } catch (err) { setError(err.detalle ?? err.message); }
  }

  async function reiniciar(u) {
    const clave = window.prompt(
      `Nueva contraseña para ${u.usuario} (mínimo 8 caracteres).\n` +
      `Sus sesiones abiertas se cerrarán.`
    );
    if (!clave) return;
    setError(null); setAviso(null);
    try {
      await api.reiniciarClave(u.id, clave);
      setAviso(`Contraseña de ${u.usuario} actualizada.`);
    } catch (err) { setError(err.detalle ?? err.message); }
  }

  const campo = (k) => ({
    value: form[k],
    onChange: (e) => setForm({ ...form, [k]: e.target.value }),
    className: `${CAMPO} mt-1`,
  });

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <button onClick={onVolver} className="rotulo mb-8 hover:text-tinta">
        ← Encargos
      </button>

      <header className="mb-8 border-b border-regla pb-6">
        <p className="rotulo">Administración</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Usuarios</h1>
      </header>

      {error && <div className="mb-6"><Aviso tono="error">{String(error)}</Aviso></div>}
      {aviso && <div className="mb-6"><Aviso tono="ok">{aviso}</Aviso></div>}

      {!creando ? (
        <>
          <div className="mb-4 flex items-center justify-between">
            <p className="rotulo">{lista.length} usuarios</p>
            <Boton onClick={() => setCreando(true)}>Nuevo usuario</Boton>
          </div>

          <div className="overflow-x-auto panel">
            <table className="w-full text-sm">
              <thead className="border-b border-regla bg-papel-hondo">
                <tr className="rotulo text-left">
                  <th className="px-3 py-2 font-normal">Usuario</th>
                  <th className="px-3 py-2 font-normal">Nombre</th>
                  <th className="px-3 py-2 font-normal">Rol</th>
                  <th className="px-3 py-2 font-normal">Estado</th>
                  <th className="px-3 py-2 font-normal">Último acceso</th>
                  <th className="px-3 py-2 font-normal">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {lista.map((u) => (
                  <tr key={u.id} className="border-b border-regla-fina hover:bg-papel-hondo">
                    <td className="cifra px-3 py-2">
                      {u.usuario}
                      {u.usuario === yo.usuario && (
                        <span className="rotulo ml-2 text-verde">usted</span>
                      )}
                    </td>
                    <td className="px-3 py-2">{u.nombre}</td>
                    <td className="px-3 py-2 text-xs">{u.rol}</td>
                    <td className={`px-3 py-2 text-xs ${u.activo ? "" : "text-rojo"}`}>
                      {u.activo ? "activo" : "inactivo"}
                    </td>
                    <td className="cifra px-3 py-2 text-xs text-tinta-suave">
                      {u.ultimo_acceso ? fecha(u.ultimo_acceso) : "nunca"}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex gap-3">
                        <button onClick={() => reiniciar(u)}
                                className="rotulo text-tinta-suave hover:text-tinta">
                          Clave
                        </button>
                        <button onClick={() => cambiarRol(u)}
                                className="rotulo text-tinta-suave hover:text-tinta">
                          {u.rol === "ADMIN" ? "Quitar admin" : "Hacer admin"}
                        </button>
                        <button onClick={() => alternarActivo(u)}
                                className={`rotulo ${u.activo ? "text-tinta-suave hover:text-rojo" : "text-verde"}`}>
                          {u.activo ? "Desactivar" : "Activar"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="mt-4 text-xs leading-relaxed text-tinta-suave">
            Los usuarios se desactivan, no se borran: los papeles de trabajo
            registran quién cargó cada archivo y quién aprobó cada
            materialidad, y ese rastro debe seguir siendo legible.
          </p>
        </>
      ) : (
        <form onSubmit={crear} className="max-w-lg">
          <p className="rotulo mb-6">Nuevo usuario</p>

          <div className="space-y-5">
            <label className="block">
              <span className="rotulo">Usuario (para entrar)</span>
              <input {...campo("usuario")} required autoComplete="off" />
            </label>
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
              <span className="mt-1 block text-xs text-tinta-suave">
                Mínimo 8 caracteres. El usuario puede cambiarla después.
              </span>
            </label>
            <label className="block">
              <span className="rotulo">Rol</span>
              <select {...campo("rol")}>
                <option value="AUDITOR">AUDITOR — usa la aplicación</option>
                <option value="ADMIN">ADMIN — además administra usuarios</option>
              </select>
            </label>
          </div>

          <div className="mt-8 flex gap-3">
            <Boton type="submit">Crear usuario</Boton>
            <Boton type="button" variante="texto"
                   onClick={() => { setCreando(false); setForm(VACIO); }}>
              Cancelar
            </Boton>
          </div>
        </form>
      )}
    </div>
  );
}
