import { useEffect, useState } from "react";
import { api, fecha } from "../api";
import { Aviso, Boton } from "../comp/Piezas";

export default function Encargos({ onAbrir }) {
  const [lista, setLista] = useState([]);
  const [creando, setCreando] = useState(false);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({
    nit: "", razon_social: "", fecha_corte: "", responsable: "",
  });

  useEffect(() => { api.encargos().then(setLista).catch((e) => setError(e.message)); }, []);

  async function crear(e) {
    e.preventDefault();
    setError(null);
    try {
      const enc = await api.crearEncargo(form);
      onAbrir(enc.id);
    } catch (err) {
      setError(err.message);
    }
  }

  const campo = (k) => ({
    value: form[k],
    onChange: (e) => setForm({ ...form, [k]: e.target.value }),
    className:
      "w-full border border-regla bg-papel-alto px-3 py-2 text-sm " +
      "focus:border-verde focus:outline-none",
  });

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <header className="mb-12 border-b border-regla pb-6">
        <p className="rotulo">Russell Bedford · Analítica</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">
          Balances y movimientos
        </h1>
        <p className="mt-2 max-w-xl text-sm text-tinta-media">
          Cargue los balances y movimientos del cliente. El sistema los valida,
          detecta recargas y deja la evidencia de lo que cambió.
        </p>
      </header>

      {error && <div className="mb-6"><Aviso tono="error">{error}</Aviso></div>}

      {!creando ? (
        <>
          <div className="mb-4 flex items-center justify-between">
            <p className="rotulo">Encargos abiertos</p>
            <Boton onClick={() => setCreando(true)}>Nuevo encargo</Boton>
          </div>

          {lista.length === 0 ? (
            <div className="border border-dashed border-regla px-6 py-16 text-center">
              <p className="text-sm text-tinta-media">
                Todavía no hay encargos. Cree el primero para empezar a cargar archivos.
              </p>
            </div>
          ) : (
            <div className="border-t border-regla">
              {lista.map((e) => (
                <button
                  key={e.id}
                  onClick={() => onAbrir(e.id)}
                  className="flex w-full items-baseline gap-6 border-b border-regla-fina py-4 text-left hover:bg-papel-hondo"
                >
                  <span className="flex-1 font-medium">{e.razon_social}</span>
                  <span className="cifra text-xs text-tinta-suave">{e.nit}</span>
                  <span className="cifra text-sm">{fecha(e.fecha_corte)}</span>
                  <span className="rotulo w-24 text-right">{e.estado}</span>
                </button>
              ))}
            </div>
          )}
        </>
      ) : (
        <form onSubmit={crear} className="max-w-lg">
          <p className="rotulo mb-6">Nuevo encargo</p>

          <div className="space-y-5">
            <label className="block">
              <span className="rotulo">NIT</span>
              <input {...campo("nit")} required placeholder="901228343-1" className={`${campo("nit").className} cifra mt-1`} />
            </label>

            <label className="block">
              <span className="rotulo">Razón social</span>
              <input {...campo("razon_social")} required placeholder="LIQUITECH S.A.S." className={`${campo("razon_social").className} mt-1`} />
            </label>

            <label className="block">
              <span className="rotulo">Fecha de corte</span>
              <input type="date" {...campo("fecha_corte")} required className={`${campo("fecha_corte").className} cifra mt-1`} />
              <span className="mt-1 block text-xs text-tinta-suave">
                Los dos periodos comparativos se calculan a partir de esta fecha.
                Las materialidades se registran después, en su pestaña.
              </span>
            </label>

            <label className="block">
              <span className="rotulo">Responsable</span>
              <input {...campo("responsable")} className={`${campo("responsable").className} mt-1`} />
            </label>
          </div>

          <div className="mt-8 flex gap-3">
            <Boton type="submit">Abrir encargo</Boton>
            <Boton type="button" variante="texto" onClick={() => setCreando(false)}>
              Cancelar
            </Boton>
          </div>
        </form>
      )}
    </div>
  );
}
