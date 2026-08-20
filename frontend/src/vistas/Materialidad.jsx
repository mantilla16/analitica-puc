import { useEffect, useState } from "react";
import { api, monto } from "../api";
import { Aviso, Boton, Punteo } from "../comp/Piezas";

const AYUDA = {
  PLANEACION:
    "Se fija al planear el trabajo. Es la referencia de la que suelen derivarse las demás.",
  EJECUCION:
    "Performance materiality. Más baja que la de planeación para dejar margen a la acumulación de hallazgos pequeños.",
  CIERRE:
    "Se revisa al concluir, cuando ya se conocen las cifras definitivas.",
};

/**
 * Tres materialidades, una por fase. Los valores los digita el auditor:
 * el sistema no los deriva ni los inventa. Cada una se puede aplicar o no.
 */
export default function Materialidad({ encargoId, onCambio }) {
  const [d, setD] = useState(null);
  const [borrador, setBorrador] = useState({});
  const [param, setParam] = useState({ pct_variacion: "20", pct_trivialidad: "5" });
  const [error, setError] = useState(null);
  const [guardado, setGuardado] = useState(null);

  useEffect(() => { cargar(); }, [encargoId]);

  async function cargar() {
    try {
      const r = await api.materialidades(encargoId);
      setD(r);
      const b = {};
      r.materialidades.forEach((m) => {
        b[m.fase] = {
          valor: m.valor ?? "",
          porcentaje: m.porcentaje ?? "",
          aplicar: m.aplicar,
        };
      });
      setBorrador(b);
      setParam({
        pct_variacion: String(r.pct_variacion ?? 20),
        pct_trivialidad: String(r.pct_trivialidad ?? 5),
      });
    } catch (e) { setError(e.message); }
  }

  if (error) return <Aviso tono="error">{error}</Aviso>;
  if (!d) return <p className="text-sm text-tinta-suave">Cargando…</p>;

  const editar = (fase, campo, v) =>
    setBorrador({ ...borrador, [fase]: { ...borrador[fase], [campo]: v } });

  async function guardar(fase) {
    setError(null);
    const b = borrador[fase];
    try {
      await api.guardarMaterialidad(encargoId, fase, {
        valor: b.valor === "" ? null : Number(b.valor),
        porcentaje: b.porcentaje === "" ? null : Number(b.porcentaje),
        aplicar: b.aplicar,
      });
      setGuardado(fase);
      setTimeout(() => setGuardado(null), 2000);
      await cargar();
      onCambio?.();
    } catch (e) { setError(e.message); }
  }

  async function guardarParametros() {
    await api.guardarParametros(encargoId, {
      pct_variacion: Number(param.pct_variacion),
      pct_trivialidad: Number(param.pct_trivialidad),
    });
    await cargar();
    onCambio?.();
  }

  async function activar(fase) {
    await api.fijarFase(encargoId, fase);
    await cargar();
    onCambio?.();
  }

  const planeacion = d.materialidades.find((m) => m.fase === "PLANEACION");
  const refValor = Number(planeacion?.valor) || 0;

  return (
    <div className="space-y-10">
      <div>
        <p className="rotulo mb-1">Materialidad por fase</p>
        <p className="max-w-2xl text-sm text-tinta-media">
          El ejercicio se corre en tres fases. Cada una tiene su propia
          materialidad y usted decide cuáles aplicar. Los valores los define el
          equipo del encargo; el sistema no los calcula.
        </p>
      </div>

      <div className="space-y-px bg-regla">
        {d.materialidades.map((m) => {
          const b = borrador[m.fase] ?? {};
          const activa = d.fase_activa === m.fase;
          const sugerido =
            m.fase !== "PLANEACION" && refValor && b.porcentaje
              ? (refValor * Number(b.porcentaje)) / 100
              : null;

          return (
            <div key={m.fase}
                 className={`bg-papel-alto p-5 ${activa ? "border-l-2 border-verde" : "border-l-2 border-transparent"}`}>
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <span className="rotulo">{m.fase_nombre}</span>
                <span className="font-medium">{m.nombre}</span>
                {activa && (
                  <span className="rotulo flex items-center gap-1 text-verde">
                    <Punteo tam={13} /> fase en curso
                  </span>
                )}
                {!activa && (
                  <button onClick={() => activar(m.fase)}
                          className="rotulo hover:text-tinta">
                    usar esta fase
                  </button>
                )}
                {guardado === m.fase && (
                  <span className="rotulo text-verde">guardado</span>
                )}
              </div>

              <p className="mb-4 max-w-2xl text-xs leading-relaxed text-tinta-suave">
                {AYUDA[m.fase]}
              </p>

              <div className="flex flex-wrap items-end gap-5">
                <label className="block">
                  <span className="rotulo">Valor en pesos</span>
                  <input
                    type="number" step="0.01" value={b.valor ?? ""}
                    onChange={(e) => editar(m.fase, "valor", e.target.value)}
                    placeholder="0"
                    className="cifra mt-1 w-56 border border-regla bg-papel px-3 py-2 text-sm"
                  />
                </label>

                {m.fase !== "PLANEACION" && (
                  <label className="block">
                    <span className="rotulo">% de la de planeación</span>
                    <input
                      type="number" step="0.01" value={b.porcentaje ?? ""}
                      onChange={(e) => editar(m.fase, "porcentaje", e.target.value)}
                      className="cifra mt-1 w-28 border border-regla bg-papel px-3 py-2 text-sm"
                    />
                  </label>
                )}

                <label className="flex items-center gap-2 pb-2 text-sm">
                  <input type="checkbox" checked={b.aplicar ?? false}
                         onChange={(e) => editar(m.fase, "aplicar", e.target.checked)} />
                  Aplicar
                </label>

                <Boton variante="contorno" onClick={() => guardar(m.fase)}>
                  Guardar
                </Boton>
              </div>

              {sugerido > 0 && Number(b.valor) !== Math.round(sugerido * 100) / 100 && (
                <p className="mt-3 text-xs text-tinta-suave">
                  El {b.porcentaje}% de la materialidad de planeación sería{" "}
                  <button
                    onClick={() => editar(m.fase, "valor", sugerido.toFixed(2))}
                    className="cifra underline underline-offset-4 hover:text-verde"
                  >
                    {monto(sugerido)}
                  </button>
                  . Es una referencia, no se aplica sola.
                </p>
              )}
            </div>
          );
        })}
      </div>

      {/* --------------------------------------------- criterios de selección */}
      <div className="border-t border-regla pt-6">
        <p className="rotulo mb-1">Criterios de selección</p>
        <p className="mb-4 max-w-2xl text-sm text-tinta-media">
          Aplican sobre la materialidad de la fase en curso.
        </p>

        <div className="flex flex-wrap items-end gap-5">
          <label className="block">
            <span className="rotulo">Variación mínima</span>
            <div className="mt-1 flex items-center gap-2">
              <input type="number" step="0.01" value={param.pct_variacion}
                     onChange={(e) => setParam({ ...param, pct_variacion: e.target.value })}
                     className="cifra w-24 border border-regla bg-papel px-3 py-2 text-sm" />
              <span className="text-sm text-tinta-suave">%</span>
            </div>
          </label>

          <label className="block">
            <span className="rotulo">Piso de ruido</span>
            <div className="mt-1 flex items-center gap-2">
              <input type="number" step="0.01" value={param.pct_trivialidad}
                     onChange={(e) => setParam({ ...param, pct_trivialidad: e.target.value })}
                     className="cifra w-24 border border-regla bg-papel px-3 py-2 text-sm" />
              <span className="text-sm text-tinta-suave">% de la materialidad</span>
            </div>
          </label>

          <Boton variante="contorno" onClick={guardarParametros}>Guardar</Boton>
        </div>

        <p className="mt-4 max-w-2xl text-xs leading-relaxed text-tinta-suave">
          Una cuenta se marca si su variación supera la materialidad en pesos, o
          si varía más del porcentaje indicado con un monto por encima del piso
          de ruido. Sin ese piso, una cuenta que pasa de 2 a 10 millones aparece
          como “+400%” y llena el informe de ruido.
        </p>
      </div>
    </div>
  );
}
