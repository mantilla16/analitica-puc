import { useState } from "react";
import { api } from "../api";
import { Aviso, Boton } from "../comp/Piezas";

/** Puerta de entrada. La sesión viaja en una cookie HttpOnly que pone el
 *  servidor: aquí no se guarda ningún token, así que nada que un script
 *  ajeno pueda leer del navegador. */
export default function Login({ onEntrar }) {
  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);

  async function entrar(e) {
    e.preventDefault();
    setError(null);
    setOcupado(true);
    try {
      onEntrar(await api.login(usuario.trim(), clave));
    } catch (err) {
      setError(err.estado === 401
        ? "Usuario o contraseña incorrectos."
        : err.message);
      setClave("");
    } finally {
      setOcupado(false);
    }
  }

  const campo = "w-full border border-regla bg-papel-alto px-3 py-2 text-sm " +
                "focus:border-verde focus:outline-none";

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6">
      <header className="mb-8 border-b border-regla pb-6">
        <p className="rotulo">Russell Bedford · Analítica</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          Balances y movimientos
        </h1>
      </header>

      {error && <div className="mb-5"><Aviso tono="error">{error}</Aviso></div>}

      <form onSubmit={entrar} className="space-y-5">
        <label className="block">
          <span className="rotulo">Usuario</span>
          <input value={usuario} onChange={(e) => setUsuario(e.target.value)}
                 required autoFocus autoComplete="username"
                 className={`${campo} mt-1`} />
        </label>

        <label className="block">
          <span className="rotulo">Contraseña</span>
          <input type="password" value={clave} onChange={(e) => setClave(e.target.value)}
                 required autoComplete="current-password"
                 className={`${campo} mt-1`} />
        </label>

        <Boton type="submit" disabled={ocupado}>
          {ocupado ? "Entrando…" : "Entrar"}
        </Boton>
      </form>

      <p className="mt-8 text-xs leading-relaxed text-tinta-suave">
        Esta herramienta contiene información contable de clientes de
        auditoría. No comparta sus credenciales.
      </p>
    </div>
  );
}
