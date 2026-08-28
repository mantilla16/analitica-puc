import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Aviso, Boton, Chip, Modal } from "./Piezas";

/* Iconos de trazo, del mismo grosor que el punteo: no son adornos, son
   pistas de qué hace cada opción cuando se lee de reojo. */
const Icono = ({ d }) => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true"
       stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
       strokeLinejoin="round" className="shrink-0 opacity-70">
    <path d={d} />
  </svg>
);
const TRAZO = {
  bitacora: "M8 6h11M8 12h11M8 18h11M3.5 6h.01M3.5 12h.01M3.5 18h.01",
  usuarios: "M16 19v-1a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v1M9.5 7.5a3 3 0 1 0 0 .01M17 11h4M19 9v4",
  clave: "M7 11V8a5 5 0 0 1 10 0v3M5 11h14v9H5z",
  salir: "M15 17l5-5-5-5M20 12H9M11 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h5",
};

/**
 * Todo lo de la cuenta en un solo lugar. Antes eran botones sueltos en la
 * esquina: cada opción nueva competía con las demás por atención, y aun
 * así faltaba lo más básico -- cambiar la propia contraseña.
 */
export default function MenuUsuario({ yo, vista, onIr, onSalir }) {
  const [abierto, setAbierto] = useState(false);
  const [cambiando, setCambiando] = useState(false);
  const caja = useRef(null);

  /* Cerrar al hacer clic fuera o con Escape: un menú que solo se cierra
     con su propio botón atrapa al usuario. */
  useEffect(() => {
    if (!abierto) return;
    const fuera = (e) => { if (!caja.current?.contains(e.target)) setAbierto(false); };
    const escape = (e) => { if (e.key === "Escape") setAbierto(false); };
    document.addEventListener("mousedown", fuera);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", fuera);
      document.removeEventListener("keydown", escape);
    };
  }, [abierto]);

  const ir = (v) => { setAbierto(false); onIr(v); };
  const opcion = "flex w-full items-center gap-2.5 rounded-[8px] px-2.5 py-2 " +
                 "text-left text-sm transition-colors hover:bg-papel-hondo";

  return (
    <div ref={caja} className="relative">
      <button onClick={() => setAbierto(!abierto)}
              aria-haspopup="menu" aria-expanded={abierto}
              className={`flex items-center gap-2.5 rounded-full py-1 pl-1 pr-3
                          transition-colors ${abierto ? "bg-papel-hondo" : "hover:bg-papel-hondo"}`}>
        <span className="flex h-7 w-7 items-center justify-center rounded-full
                         bg-marca text-xs font-bold text-papel-alto">
          {yo.nombre.trim().charAt(0).toUpperCase()}
        </span>
        <span className="hidden text-sm font-semibold sm:inline">{yo.nombre}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
             strokeLinejoin="round" aria-hidden="true"
             className={`opacity-50 transition-transform ${abierto ? "rotate-180" : ""}`}>
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {abierto && (
        <div role="menu"
             className="panel deslizar absolute right-0 z-30 mt-2 w-60 p-1.5
                        shadow-[var(--sombra-alta)]">
          <div className="border-b border-regla-fina px-2.5 pb-2.5 pt-1.5">
            <p className="truncate text-sm font-semibold">{yo.nombre}</p>
            <div className="mt-1 flex items-center gap-2">
              <span className="cifra text-xs text-tinta-suave">{yo.usuario}</span>
              {yo.rol === "ADMIN" && <Chip tono="morado">admin</Chip>}
            </div>
          </div>

          <div className="py-1">
            {yo.rol === "ADMIN" && (
              <>
                <button className={opcion} onClick={() => ir("bitacora")}>
                  <Icono d={TRAZO.bitacora} />
                  Bitácora
                  {vista === "bitacora" && (
                    <span className="ml-auto h-1.5 w-1.5 rounded-full bg-cian" />
                  )}
                </button>
                <button className={opcion} onClick={() => ir("usuarios")}>
                  <Icono d={TRAZO.usuarios} />
                  Usuarios
                  {vista === "usuarios" && (
                    <span className="ml-auto h-1.5 w-1.5 rounded-full bg-cian" />
                  )}
                </button>
              </>
            )}
            <button className={opcion}
                    onClick={() => { setAbierto(false); setCambiando(true); }}>
              <Icono d={TRAZO.clave} />
              Cambiar contraseña
            </button>
          </div>

          <div className="border-t border-regla-fina pt-1">
            <button className={`${opcion} text-rojo hover:bg-rojo-tenue`}
                    onClick={onSalir}>
              <Icono d={TRAZO.salir} />
              Cerrar sesión
            </button>
          </div>
        </div>
      )}

      {cambiando && <CambiarClave onCerrar={() => setCambiando(false)} />}
    </div>
  );
}

/** Cambio de la propia contraseña. Exige la actual: si alguien deja la
 *  sesión abierta, no puede quedarse con la cuenta. */
function CambiarClave({ onCerrar }) {
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [repetida, setRepetida] = useState("");
  const [error, setError] = useState(null);
  const [listo, setListo] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  async function guardar(e) {
    e.preventDefault();
    setError(null);
    if (nueva !== repetida) return setError("Las contraseñas nuevas no coinciden.");
    setOcupado(true);
    try {
      await api.cambiarMiClave(actual, nueva);
      setListo(true);
    } catch (err) {
      setError(err.estado === 403
        ? "La contraseña actual no coincide."
        : (err.detalle ?? err.message));
    } finally { setOcupado(false); }
  }

  const campo = "w-full px-3 py-2 text-sm";

  return (
    <Modal rotulo="Su cuenta" titulo="Cambiar contraseña" onCerrar={onCerrar}>
        {listo ? (
          <>
            <Aviso tono="ok">Contraseña actualizada.</Aviso>
            <div className="mt-5 flex justify-end">
              <Boton variante="contorno" onClick={onCerrar}>Listo</Boton>
            </div>
          </>
        ) : (
          <form onSubmit={guardar} className="space-y-4">
            {error && <Aviso tono="error">{String(error)}</Aviso>}
            <label className="block">
              <span className="rotulo">Contraseña actual</span>
              <input type="password" value={actual} required autoFocus
                     autoComplete="current-password"
                     onChange={(e) => setActual(e.target.value)}
                     className={`${campo} mt-1.5`} />
            </label>
            <label className="block">
              <span className="rotulo">Nueva contraseña</span>
              <input type="password" value={nueva} required minLength={8}
                     autoComplete="new-password"
                     onChange={(e) => setNueva(e.target.value)}
                     className={`${campo} mt-1.5`} />
              <span className="mt-1 block text-xs text-tinta-suave">
                Mínimo 8 caracteres.
              </span>
            </label>
            <label className="block">
              <span className="rotulo">Repetir la nueva</span>
              <input type="password" value={repetida} required
                     autoComplete="new-password"
                     onChange={(e) => setRepetida(e.target.value)}
                     className={`${campo} mt-1.5`} />
            </label>
            <div className="flex gap-3 pt-1">
              <Boton type="submit" disabled={ocupado}>
                {ocupado ? "Guardando…" : "Cambiar"}
              </Boton>
              <Boton type="button" variante="texto" onClick={onCerrar}>
                Cancelar
              </Boton>
            </div>
          </form>
      )}
    </Modal>
  );
}
