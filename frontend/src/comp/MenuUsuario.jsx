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
 * así faltaba lo más básico -- corregir sus propios datos.
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
              Mis datos
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

      {cambiando && <MisDatos yo={yo} onCerrar={() => setCambiando(false)} />}
    </div>
  );
}

/** Los datos con que la persona firma sus papeles.
 *
 *  Ya no hay contraseña que cambiar, pero sí hace falta poder corregir un
 *  nombre mal escrito o agregar la tarjeta profesional después: son los
 *  datos que salen impresos en el papel de trabajo, y un dato equivocado
 *  ahí se propaga a todo lo que se firme.
 *
 *  Escribe contra el mismo endpoint del registro inicial, que solo marca
 *  la fecha de registro si estaba vacía -- así corregir datos después no
 *  reabre el formulario obligatorio.
 */
function MisDatos({ yo, onCerrar }) {
  const [d, setD] = useState({
    nombre: yo?.nombre ?? "",
    cargo: yo?.cargo ?? "",
    tarjeta_profesional: yo?.tarjeta_profesional ?? "",
    telefono: yo?.telefono ?? "",
  });
  const [error, setError] = useState(null);
  const [listo, setListo] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  const puedeGuardar = d.nombre.trim().split(/\s+/).length >= 2;

  async function guardar(e) {
    e.preventDefault();
    setError(null);
    setOcupado(true);
    try {
      await api.registrarme(d);
      setListo(true);
    } catch (err) {
      setError(err.detalle ?? err.message);
    } finally { setOcupado(false); }
  }

  const campo = "w-full px-3 py-2 text-sm";
  const set = (k) => (e) => setD({ ...d, [k]: e.target.value });

  return (
    <Modal rotulo="Su cuenta" titulo="Mis datos" onCerrar={onCerrar}
           ancho="max-w-md">
      {listo ? (
        <>
          <Aviso tono="ok">
            Datos actualizados. Se verán reflejados al recargar.
          </Aviso>
          <div className="mt-5 flex justify-end">
            <Boton variante="contorno" onClick={onCerrar}>Listo</Boton>
          </div>
        </>
      ) : (
        <form onSubmit={guardar} className="space-y-4">
          {error && <Aviso tono="error">{String(error)}</Aviso>}

          <p className="text-xs leading-relaxed text-tinta-suave">
            Entra con <span className="cifra">{yo?.correo}</span>. El correo
            es su identidad en el sistema y no se cambia desde aquí: pídalo
            a un administrador.
          </p>

          <label className="block">
            <span className="rotulo">Nombre y apellidos</span>
            <input value={d.nombre} onChange={set("nombre")} required autoFocus
                   autoComplete="name" className={`${campo} mt-1.5`} />
          </label>

          <label className="block">
            <span className="rotulo">Cargo</span>
            <input value={d.cargo} onChange={set("cargo")}
                   placeholder="Auditor senior, revisor fiscal…"
                   className={`${campo} mt-1.5`} />
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="rotulo">Tarjeta profesional</span>
              <input value={d.tarjeta_profesional}
                     onChange={set("tarjeta_profesional")}
                     className={`${campo} mt-1.5 cifra`} />
            </label>
            <label className="block">
              <span className="rotulo">Teléfono</span>
              <input value={d.telefono} onChange={set("telefono")}
                     inputMode="tel" className={`${campo} mt-1.5 cifra`} />
            </label>
          </div>

          <div className="flex gap-3 pt-1">
            <Boton type="submit" disabled={ocupado || !puedeGuardar}>
              {ocupado ? "Guardando…" : "Guardar"}
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
