import { useEffect, useState } from "react";
import { api } from "../api";
import { Anillo, Aviso, Boton } from "../comp/Piezas";
import { signIn, completeRedirect, describeError, limpiarFragmento } from "../lib/msal";

/* Lo que se promete aquí es lo que la herramienta realmente hace. Poner
   beneficios genéricos en una pantalla de ingreso interna no informa a
   nadie: quien entra ya sabe para qué viene. */
const CAPACIDADES = [
  ["Cuadre por nivel", "Cada nivel del balance debe sumar cero. Se verifica al cargar."],
  ["Comparativo del periodo", "Clases 1 a 3 contra el cierre; 4 a 7 contra el mismo corte del año anterior."],
  ["Observaciones asistidas", "Redactadas sobre cifras ya calculadas, y verificadas contra ellas."],
];

/**
 * Ingreso con la cuenta de Microsoft 365 de la firma.
 *
 * MSAL autentica en el navegador, devuelve un id_token firmado por
 * Microsoft, y el backend lo verifica. No hay contraseñas, ni códigos por
 * correo, ni un flujo de "primera vez": el nombre viene con el token, así
 * que la cuenta queda utilizable al primer ingreso.
 *
 * La sesión viaja en una cookie HttpOnly que pone el servidor: aquí no se
 * guarda ningún token, así que no hay nada que un script ajeno pueda leer
 * del navegador.
 */
export default function Login({ onEntrar }) {
  const [error, setError] = useState(null);
  const [cfg, setCfg] = useState(null);
  /* Al volver de Microsoft la URL trae el código en el fragmento. Se
     arranca ya en "conectando" para no mostrar el botón un instante antes
     de completar el ingreso. */
  const [conectando, setConectando] = useState(
    () => typeof window !== "undefined" && /[#&](code|error)=/.test(window.location.hash),
  );

  useEffect(() => { api.estadoAuth().then(setCfg).catch(() => setCfg(null)); }, []);

  /* Vuelta de Microsoft: se recoge el id_token del fragmento y se cambia
     por una sesión del backend. Si no hay nada que completar -- por
     ejemplo al cerrar sesión con el fragmento todavía en la barra --, se
     apaga el estado en vez de dejar la pantalla girando. */
  useEffect(() => {
    if (!cfg) return;
    const listo = cfg.msClientId && cfg.msTenantId;
    if (!listo) {
      if (conectando) { setConectando(false); limpiarFragmento(); }
      return;
    }
    let cancelado = false;
    completeRedirect(cfg)
      .then((idToken) => {
        if (cancelado) return;
        if (!idToken) return setConectando(false);
        setConectando(true);
        return api.loginMicrosoft(idToken).then(onEntrar);
      })
      .catch((err) => {
        if (cancelado) return;
        setError(describeError(err));
        setConectando(false);
      });
    return () => { cancelado = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg]);

  async function entrar() {
    setError(null);
    setConectando(true);
    try {
      await signIn(cfg);          // no retorna: la pestaña navega
    } catch (err) {
      setError(describeError(err));
      setConectando(false);
    }
  }

  const dominio = cfg?.dominio ?? "rbcol.co";
  const listo = Boolean(cfg?.msClientId && cfg?.msTenantId);

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">

      <aside className="marca-fondo relative hidden flex-col justify-between
                        overflow-hidden p-12 text-white lg:flex">
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

        <p className="relative text-xs text-white/45">taking you further</p>
      </aside>

      <main className="flex flex-col justify-center bg-papel-alto px-6 py-12 sm:px-14">
        <div className="mx-auto w-full max-w-sm">

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
            Con su cuenta institucional{" "}
            <span className="cifra">@{dominio}</span>.
          </p>

          {/* El servidor sin msClientId/msTenantId significa que Microsoft
              no está configurado. Se dice antes de que la persona pulse un
              botón que no puede hacer nada. */}
          {cfg && !listo && (
            <div className="mt-6">
              <Aviso tono="error" titulo="Ingreso no disponible">
                El login con Microsoft no está configurado en el servidor.
                Avise al administrador.
              </Aviso>
            </div>
          )}

          {error && <div className="mt-6"><Aviso tono="error">{error}</Aviso></div>}

          <div className="mt-8">
            <Boton onClick={entrar} disabled={!listo || conectando}
                   className="w-full justify-center gap-3">
              {/* Cuatro cuadros de la marca Microsoft, sin depender de
                  imágenes externas. */}
              <svg width="16" height="16" viewBox="0 0 21 21" aria-hidden="true">
                <rect x="1"  y="1"  width="9" height="9" fill="#f25022"/>
                <rect x="11" y="1"  width="9" height="9" fill="#7fba00"/>
                <rect x="1"  y="11" width="9" height="9" fill="#00a4ef"/>
                <rect x="11" y="11" width="9" height="9" fill="#ffb900"/>
              </svg>
              {conectando ? "Conectando…" : "Entrar con Microsoft"}
            </Boton>
          </div>

          <p className="mt-10 border-t border-regla pt-5 text-xs leading-relaxed
                        text-tinta-suave">
            Esta herramienta contiene información contable de clientes de
            auditoría. No deje la sesión abierta en equipos compartidos.
          </p>
        </div>
      </main>
    </div>
  );
}
