import { useState } from "react";
import { api } from "../api";
import { Anillo, Aviso, Boton } from "../comp/Piezas";

/* Lo que se promete aquí es lo que la herramienta realmente hace. Poner
   beneficios genéricos en una pantalla de ingreso interna no informa a
   nadie: quien entra ya sabe para qué viene. */
const CAPACIDADES = [
  ["Cuadre por nivel", "Cada nivel del balance debe sumar cero. Se verifica al cargar."],
  ["Comparativo del periodo", "Clases 1 a 3 contra el cierre; 4 a 7 contra el mismo corte del año anterior."],
  ["Observaciones asistidas", "Redactadas sobre cifras ya calculadas, y verificadas contra ellas."],
];

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

  const campo = "w-full px-3.5 py-2.5 text-sm";

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">

      {/* ------------------------------------------------------- marca */}
      {/* Se oculta en pantallas angostas: ahí el formulario manda y la
          marca se reduce al anillo pequeño del otro lado. */}
      <aside className="marca-fondo relative hidden flex-col justify-between
                        overflow-hidden p-12 text-white lg:flex">
        {/* Anillo desbordado, como textura de fondo y no como logotipo */}
        <Anillo tam={720} grosor={6}
                className="anillo-lento pointer-events-none absolute
                           -right-40 -bottom-40 opacity-[0.18]" />

        <div className="relative flex items-center gap-3">
          <Anillo tam={34} grosor={16} />
          <span className="text-lg font-bold tracking-tight">Russell Bedford</span>
        </div>

        <div className="relative max-w-md">
          <h1 className="text-[2.6rem] font-bold leading-[1.1] tracking-tight">
            Analítica de balances<br />y movimientos
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-white/70">
            Carga, valida y compara los estados del encargo. Deja la
            evidencia de lo que cambió y por qué.
          </p>

          <dl className="mt-10 space-y-5">
            {CAPACIDADES.map(([titulo, detalle]) => (
              <div key={titulo} className="flex gap-3">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cian" />
                <div>
                  <dt className="text-sm font-semibold">{titulo}</dt>
                  <dd className="text-xs leading-relaxed text-white/60">{detalle}</dd>
                </div>
              </div>
            ))}
          </dl>
        </div>

        <p className="relative text-xs text-white/45">
          taking you further
        </p>
      </aside>

      {/* -------------------------------------------------- formulario */}
      {/* Blanco declarado, no heredado del fondo de la página: junto al
          navy del panel de marca, un papel tintado se ve sucio. */}
      <main className="flex flex-col justify-center bg-papel-alto px-6 py-12 sm:px-14">
        <div className="mx-auto w-full max-w-sm">

          {/* Marca compacta, solo donde el panel lateral no cabe */}
          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <Anillo tam={32} grosor={16} />
            <span className="font-bold tracking-tight text-marca">
              Russell Bedford
            </span>
          </div>

          <p className="rotulo">Analítica PUC</p>
          <h2 className="mt-1.5 text-2xl font-bold tracking-tight">
            Ingrese a su cuenta
          </h2>
          <p className="mt-2 text-sm text-tinta-media">
            Use las credenciales que le asignó el administrador.
          </p>

          {error && <div className="mt-6"><Aviso tono="error">{error}</Aviso></div>}

          <form onSubmit={entrar} className="mt-8 space-y-5">
            <label className="block">
              <span className="rotulo">Usuario</span>
              <input value={usuario} onChange={(e) => setUsuario(e.target.value)}
                     required autoFocus autoComplete="username"
                     className={`${campo} mt-1.5`} />
            </label>

            <label className="block">
              <span className="rotulo">Contraseña</span>
              <input type="password" value={clave}
                     onChange={(e) => setClave(e.target.value)}
                     required autoComplete="current-password"
                     className={`${campo} mt-1.5`} />
            </label>

            <Boton type="submit" disabled={ocupado}
                   className="w-full justify-center">
              {ocupado ? "Entrando…" : "Entrar"}
            </Boton>
          </form>

          <p className="mt-10 border-t border-regla pt-5 text-xs leading-relaxed
                        text-tinta-suave">
            Esta herramienta contiene información contable de clientes de
            auditoría. No comparta sus credenciales ni deje la sesión
            abierta en equipos compartidos.
          </p>
        </div>
      </main>
    </div>
  );
}
