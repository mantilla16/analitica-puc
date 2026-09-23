import { useEffect, useRef, useState } from "react";
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

const campo = "w-full px-3.5 py-2.5 text-sm";

/**
 * Ingreso en dos pasos: correo del dominio, y el código que llega a ese
 * buzón. No hay contraseña que recordar ni que compartir.
 *
 * La sesión viaja en una cookie HttpOnly que pone el servidor: aquí no se
 * guarda ningún token, así que no hay nada que un script ajeno pueda leer
 * del navegador.
 */
export default function Login({ onEntrar }) {
  const [paso, setPaso] = useState("correo");       // correo | codigo
  const [correo, setCorreo] = useState("");
  const [codigo, setCodigo] = useState("");
  const [error, setError] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [cfg, setCfg] = useState(null);
  const [segundos, setSegundos] = useState(0);
  /* Al volver de Microsoft la URL trae el código en el fragmento. Se
     arranca ya en "conectando" para no mostrar el botón un instante
     antes de entrar. */
  const [conectandoMS, setConectandoMS] = useState(
    () => typeof window !== "undefined" && /[#&](code|error)=/.test(window.location.hash),
  );
  const campoCodigo = useRef(null);

  useEffect(() => { api.estadoAuth().then(setCfg).catch(() => setCfg(null)); }, []);

  /* Vuelta de Microsoft: se recoge el id_token del fragmento y se cambia
     por una sesión del backend. Si no hay nada que completar -- por
     ejemplo, al cerrar sesión con el fragmento todavía en la barra --,
     se apaga el estado en vez de dejar la pantalla girando. */
  useEffect(() => {
    if (!cfg) return;
    const listo = cfg.msClientId && cfg.msTenantId;
    if (!listo) {
      if (conectandoMS) { setConectandoMS(false); limpiarFragmento(); }
      return;
    }
    let cancelado = false;
    completeRedirect(cfg)
      .then((idToken) => {
        if (cancelado) return;
        if (!idToken) return setConectandoMS(false);
        setConectandoMS(true);
        return api.loginMicrosoft(idToken).then(onEntrar);
      })
      .catch((err) => {
        if (cancelado) return;
        setError(describeError(err));
        setConectandoMS(false);
      });
    return () => { cancelado = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg]);

  async function entrarConMicrosoft() {
    setError(null);
    setConectandoMS(true);
    try {
      await signIn(cfg);          // no retorna: la pestaña navega
    } catch (err) {
      setError(describeError(err));
      setConectandoMS(false);
    }
  }

  // Cuenta atrás para poder reenviar. Sin esto la gente pulsa "reenviar"
  // tres veces en diez segundos y se topa con el límite del servidor sin
  // entender por qué.
  useEffect(() => {
    if (segundos <= 0) return;
    const t = setTimeout(() => setSegundos((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [segundos]);

  useEffect(() => {
    if (paso === "codigo") campoCodigo.current?.focus();
  }, [paso]);

  const dominio = cfg?.dominio ?? "rbcol.co";
  const largo = cfg?.largo_codigo ?? 6;

  async function enviarCodigo(e) {
    e?.preventDefault();
    setError(null);
    setOcupado(true);
    try {
      const r = await api.pedirCodigo(correo.trim());
      setPaso("codigo");
      setCodigo("");
      setSegundos(45);
      setAviso(`Le enviamos un código a ${correo.trim().toLowerCase()}. `
               + `Vence en ${r.minutos} minutos.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setOcupado(false);
    }
  }

  async function entrar(e) {
    e.preventDefault();
    setError(null);
    setOcupado(true);
    try {
      onEntrar(await api.verificarCodigo(correo.trim(), codigo));
    } catch (err) {
      setError(err.message);
      setCodigo("");
      campoCodigo.current?.focus();
    } finally {
      setOcupado(false);
    }
  }

  function volverAlCorreo() {
    setPaso("correo");
    setCodigo("");
    setError(null);
    setAviso(null);
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">

      {/* ------------------------------------------------------- marca */}
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

      {/* -------------------------------------------------- formulario */}
      <main className="flex flex-col justify-center bg-papel-alto px-6 py-12 sm:px-14">
        <div className="mx-auto w-full max-w-sm">

          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <Anillo tam={32} grosor={16} />
            <span className="font-bold tracking-tight text-marca">
              Russell Bedford
            </span>
          </div>

          <p className="rotulo">Analítica PUC</p>

          {/* El envío de correo sin configurar se dice ANTES de que la
              persona pida un código: si no, pediría uno que nunca sale y
              creería que su correo está mal. */}
          {cfg && !cfg.correo_listo && (
            <div className="mt-6">
              <Aviso tono="error" titulo="El envío de correo no está configurado">
                {cfg.correo_problema} · Nadie puede recibir códigos hasta que
                se configure en el servidor.
              </Aviso>
            </div>
          )}
          {/* CONSOLA es el unico modo que no envia nada. RELAY y SMTP si
              envian, asi que no se avisa de ellos. */}
          {cfg?.modo_correo === "CONSOLA" && (
            <div className="mt-6">
              <Aviso tono="alerta" titulo="Modo consola">
                Los códigos se escriben en el registro del servidor en vez de
                enviarse. Es para pruebas: no debe quedar así.
              </Aviso>
            </div>
          )}

          {paso === "correo" ? (
            <>
              <h2 className="mt-1.5 text-2xl font-bold tracking-tight">
                Ingrese a su cuenta
              </h2>
              <p className="mt-2 text-sm text-tinta-media">
                Con su cuenta institucional{" "}
                <span className="cifra">@{dominio}</span>.
              </p>

              {error && <div className="mt-6"><Aviso tono="error">{error}</Aviso></div>}

              {/* Microsoft primero. Si el servidor tiene msClientId/msTenantId
                  configurados, este es el camino que la gente debería usar:
                  sin códigos, sin buzones, con la sesión que ya tiene abierta
                  en su Outlook. El formulario de código queda debajo como
                  alternativa por si Microsoft falla. */}
              {cfg?.msClientId && cfg?.msTenantId && (
                <div className="mt-8">
                  <Boton onClick={entrarConMicrosoft}
                         disabled={conectandoMS}
                         className="w-full justify-center gap-3">
                    {/* Cuatro cuadros de la marca Microsoft, sin depender de
                        imágenes externas. */}
                    <svg width="16" height="16" viewBox="0 0 21 21" aria-hidden="true">
                      <rect x="1"  y="1"  width="9" height="9" fill="#f25022"/>
                      <rect x="11" y="1"  width="9" height="9" fill="#7fba00"/>
                      <rect x="1"  y="11" width="9" height="9" fill="#00a4ef"/>
                      <rect x="11" y="11" width="9" height="9" fill="#ffb900"/>
                    </svg>
                    {conectandoMS ? "Conectando…" : "Entrar con Microsoft"}
                  </Boton>

                  <div className="mt-6 flex items-center gap-3 text-xs text-tinta-suave">
                    <span className="h-px flex-1 bg-regla" />
                    <span>o con un código al correo</span>
                    <span className="h-px flex-1 bg-regla" />
                  </div>
                </div>
              )}

              <form onSubmit={enviarCodigo} className="mt-6 space-y-5">
                <label className="block">
                  <span className="rotulo">Correo</span>
                  <input type="email" value={correo} required autoFocus
                         autoComplete="username"
                         placeholder={`nombre@${dominio}`}
                         onChange={(e) => setCorreo(e.target.value)}
                         className={`${campo} mt-1.5`} />
                </label>

                <Boton type="submit" variante="contorno"
                       disabled={ocupado || !correo.trim()}
                       className="w-full justify-center">
                  {ocupado ? "Enviando…" : "Enviarme un código"}
                </Boton>
              </form>
            </>
          ) : (
            <>
              <h2 className="mt-1.5 text-2xl font-bold tracking-tight">
                Escriba el código
              </h2>
              {aviso && (
                <p className="mt-2 text-sm leading-relaxed text-tinta-media">
                  {aviso}
                </p>
              )}

              {error && <div className="mt-6"><Aviso tono="error">{error}</Aviso></div>}

              <form onSubmit={entrar} className="mt-8 space-y-5">
                <label className="block">
                  <span className="rotulo">Código de {largo} dígitos</span>
                  <input ref={campoCodigo} value={codigo} required
                         inputMode="numeric" autoComplete="one-time-code"
                         maxLength={largo} placeholder={"".padEnd(largo, "0")}
                         onChange={(e) =>
                           setCodigo(e.target.value.replace(/\D/g, ""))}
                         className={`${campo} mt-1.5 cifra text-center
                                     text-2xl tracking-[0.35em]`} />
                </label>

                <Boton type="submit"
                       disabled={ocupado || codigo.length < largo}
                       className="w-full justify-center">
                  {ocupado ? "Comprobando…" : "Entrar"}
                </Boton>
              </form>

              <div className="mt-6 flex items-center justify-between text-xs">
                <button onClick={volverAlCorreo}
                        className="btn-texto text-tinta-suave hover:text-tinta">
                  Usar otro correo
                </button>
                <button onClick={enviarCodigo}
                        disabled={ocupado || segundos > 0}
                        className="btn-texto text-tinta-suave hover:text-tinta
                                   disabled:opacity-40">
                  {segundos > 0 ? `Reenviar en ${segundos}s` : "Reenviar código"}
                </button>
              </div>
            </>
          )}

          <p className="mt-10 border-t border-regla pt-5 text-xs leading-relaxed
                        text-tinta-suave">
            Esta herramienta contiene información contable de clientes de
            auditoría. El código llega solo a su buzón y sirve una vez: no lo
            reenvíe a nadie, y no deje la sesión abierta en equipos
            compartidos.
          </p>
        </div>
      </main>
    </div>
  );
}
