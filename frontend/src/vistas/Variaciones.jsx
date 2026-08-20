import { Fragment, useEffect, useState } from "react";
import { api, monto, entero } from "../api";
import { Aviso } from "../comp/Piezas";

/** Convierte el desglose del residuo en el argumento redactado, con las
 * cuentas más grandes del grupo que sí importa (el que no llegó al umbral
 * pero tampoco es ruido). Punto de partida para la nota, no un sustituto
 * del juicio del auditor. */
function resumenAutomatico(d) {
  const g = d?.desglose_no_seleccionado;
  if (!g) return "";
  const partes = [
    `De ${monto(d.residuo_no_seleccionado)} en variaciones no seleccionadas, ` +
      `${monto(g.trivial.monto)} (${entero(g.trivial.cuentas)} cuentas) está ` +
      `por debajo del piso de trivialidad, y ${monto(g.cerca_del_umbral.monto)} ` +
      `(${entero(g.cerca_del_umbral.cuentas)} cuentas) no llegó a cruzar el ` +
      `umbral de variación.`,
  ];
  if (g.cerca_del_umbral.mayores.length) {
    const top = g.cerca_del_umbral.mayores
      .slice(0, 5)
      .map((m) => `${m.cuenta}${m.nombre ? ` (${m.nombre})` : ""}: ${monto(m.variacion)}` +
        (m.variacion_pct !== null ? ` — ${m.variacion_pct}%` : ""))
      .join("; ");
    partes.push(`Las cuentas más grandes de ese segundo grupo son: ${top}.`);
  }
  return partes.join(" ");
}

const COLOR_MOTIVO = {
  "Monto": "text-rojo",
  "Cuenta nueva": "text-ambar",
  "Cuenta cerrada": "text-ambar",
  "Comportamiento": "text-ambar",
  "Naturaleza": "text-rojo",
};

/**
 * El comparativo. Clases 1-3 contra el cierre anterior, clases 4-7
 * contra el mismo corte del año pasado. La materialidad decide qué se
 * marca para revisión.
 */
export default function Variaciones({ encargoId }) {
  const [d, setD] = useState(null);
  const [fase, setFase] = useState(null);
  const [fases, setFases] = useState([]);
  const [soloSig, setSoloSig] = useState(true);
  const [error, setError] = useState(null);
  const [obs, setObs] = useState({});
  const [cargandoObs, setCargandoObs] = useState(false);

  useEffect(() => { api.fases().then(setFases).catch(() => {}); }, []);

  useEffect(() => {
    api.variaciones(encargoId, fase)
      .then((r) => { setD(r); if (!fase && r.fase) setFase(r.fase); })
      .catch((e) => setError(e.message));
  }, [encargoId, fase]);

  useEffect(() => {
    if (!d?.listo || !d.aplica || !d.significativas) { setObs({}); return; }
    setCargandoObs(true);
    api.observaciones(encargoId, d.fase)
      .then((r) => setObs(Object.fromEntries(r.map((o) => [o.cuenta, o]))))
      .catch(() => {})
      .finally(() => setCargandoObs(false));
  }, [encargoId, d?.fase, d?.listo, d?.aplica, d?.significativas]);

  if (error) return <Aviso tono="error">{error}</Aviso>;
  if (!d) return <p className="text-sm text-tinta-suave">Calculando…</p>;

  if (!d.listo) {
    const nombres = {
      BAL_ACTUAL: "el balance del corte",
      BAL_CIERRE_ANTERIOR: "el balance a 31 de diciembre del año anterior",
      BAL_CORTE_ANTERIOR: "el balance al mismo corte del año anterior",
    };
    return (
      <Aviso tono="info" titulo="Faltan balances para comparar">
        Cargue {d.faltan.map((f) => nombres[f]).join(" y ")} en la pestaña
        Archivos. El comparativo necesita los tres.
      </Aviso>
    );
  }

  const filas = soloSig && d.aplica ? d.filas.filter((f) => f.significativa) : d.filas;

  return (
    <div className="space-y-6">
      {/* ------------------------------------------------------- fases */}
      <div className="flex flex-wrap items-center gap-1 border-b border-regla pb-3">
        <span className="rotulo mr-2">Analizar bajo la fase</span>
        {fases.map((f) => (
          <button key={f.fase} onClick={() => setFase(f.fase)}
                  className={`px-3 py-1 text-sm ${
                    d.fase === f.fase
                      ? "bg-tinta text-papel"
                      : "text-tinta-suave hover:text-tinta"}`}>
            {f.nombre}
          </button>
        ))}
      </div>

      {!d.aplica && (
        <Aviso tono="alerta" titulo="Sin materialidad aplicada en esta fase">
          Registre el valor de esta fase y márquela como aplicable en la pestaña
          Materialidad. Mientras tanto se muestran todas las cuentas, ninguna
          marcada: el sistema no inventa un umbral.
        </Aviso>
      )}

      {/* -------------------------------------------------- encabezado */}
      <div className="flex flex-wrap items-end gap-8 border-b border-regla pb-5">
        <div>
          <p className="rotulo">Cuentas para revisar</p>
          <p className="cifra mt-1 text-3xl">
            {d.aplica ? entero(d.significativas) : "—"}
          </p>
          <p className="text-xs text-tinta-suave">
            de {entero(d.total_cuentas)} cuentas
          </p>
        </div>
        <div>
          <p className="rotulo">{d.materialidad?.nombre ?? "Materialidad"}</p>
          <p className="cifra mt-1 text-lg">{d.umbral ? monto(d.umbral) : "—"}</p>
        </div>
        <div>
          <p className="rotulo">Piso de ruido · {String(d.pct_trivialidad)}%</p>
          <p className="cifra mt-1 text-lg">
            {d.trivialidad ? monto(d.trivialidad) : "—"}
          </p>
        </div>
        <label className="ml-auto flex items-center gap-2 text-sm">
          <input type="checkbox" checked={soloSig} disabled={!d.aplica}
                 onChange={(e) => setSoloSig(e.target.checked)} />
          Solo las que superan el umbral
        </label>
      </div>

      {/* ---------------------------------------------- control de alcance */}
      {d.residuo_supera_umbral ? (
        <Aviso tono="alerta" titulo="El alcance puede quedar corto">
          Las variaciones no seleccionadas suman{" "}
          <span className="cifra">{monto(d.residuo_no_seleccionado)}</span>, por
          encima del umbral de ejecución. Conviene bajar el umbral o dejar
          constancia de por qué no.
        </Aviso>
      ) : (
        <p className="text-xs text-tinta-suave">
          Lo no seleccionado suma{" "}
          <span className="cifra">{monto(d.residuo_no_seleccionado)}</span>, por
          debajo de la materialidad de esta fase.
        </p>
      )}

      {/* ------------------------------------------------ desglose del residuo */}
      {d.desglose_no_seleccionado && (
        <div className="grid grid-cols-1 gap-px bg-regla sm:grid-cols-2">
          <div className="bg-papel-alto p-4">
            <p className="rotulo">Bajo el piso de trivialidad</p>
            <p className="cifra mt-1 text-lg">
              {monto(d.desglose_no_seleccionado.trivial.monto)}
            </p>
            <p className="text-xs text-tinta-suave">
              {entero(d.desglose_no_seleccionado.trivial.cuentas)} cuentas ·
              es ruido, no aporta al argumento
            </p>
          </div>
          <div className="bg-papel-alto p-4">
            <p className="rotulo">No es trivial, pero no cruzó el umbral</p>
            <p className="cifra mt-1 text-lg">
              {monto(d.desglose_no_seleccionado.cerca_del_umbral.monto)}
            </p>
            <p className="text-xs text-tinta-suave">
              {entero(d.desglose_no_seleccionado.cerca_del_umbral.cuentas)} cuentas ·
              esto es lo que hay que argumentar
            </p>
          </div>
        </div>
      )}

      {d.desglose_no_seleccionado?.cerca_del_umbral.mayores.length > 0 && (
        <div className="border border-regla bg-papel-alto p-4">
          <p className="rotulo mb-2">Las más grandes de ese grupo</p>
          <div className="space-y-1.5 text-sm">
            {d.desglose_no_seleccionado.cerca_del_umbral.mayores.map((m) => (
              <div key={m.cuenta} className="flex justify-between gap-3">
                <span className="min-w-0 flex-1 truncate">
                  <span className="cifra">{m.cuenta}</span> · {m.nombre ?? "—"}
                </span>
                <span className="cifra shrink-0">
                  {monto(m.variacion)}
                  {m.variacion_pct !== null && (
                    <span className="ml-1 text-tinta-suave">({m.variacion_pct}%)</span>
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* -------------------------------------------------- nota de alcance */}
      {d.desglose_no_seleccionado && (
        <div className="border border-regla bg-papel-alto p-4">
          <p className="rotulo mb-2">Nota de alcance</p>
          <p className="text-sm leading-relaxed">{resumenAutomatico(d)}</p>
        </div>
      )}

      {cargandoObs && (
        <p className="text-xs text-tinta-suave">
          Generando observaciones con IA para las cuentas significativas…
        </p>
      )}

      {/* --------------------------------------------------------- tabla */}
      <div className="overflow-x-auto border border-regla bg-papel-alto">
        <table className="w-full text-sm">
          <thead className="border-b border-regla bg-papel-hondo">
            <tr className="rotulo text-left">
              <th className="px-3 py-2 font-normal">Cuenta</th>
              <th className="px-3 py-2 font-normal">Nombre</th>
              <th className="px-3 py-2 text-right font-normal">Actual</th>
              <th className="px-3 py-2 text-right font-normal">Comparativo</th>
              <th className="px-3 py-2 text-right font-normal">Variación</th>
              <th className="px-3 py-2 text-right font-normal">%</th>
              <th className="px-3 py-2 font-normal">Motivo</th>
            </tr>
          </thead>
          <tbody>
            {filas.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-10 text-center text-tinta-suave">
                  Ninguna cuenta supera el umbral. Quite el filtro para ver todas.
                </td>
              </tr>
            )}
            {filas.map((f) => (
              <Fragment key={f.cuenta}>
                <tr className="border-b border-regla-fina hover:bg-papel-hondo">
                  <td className="cifra px-3 py-2">{f.cuenta}</td>
                  <td className="max-w-xs truncate px-3 py-2" title={f.nombre}>
                    {f.nombre ?? "—"}
                  </td>
                  <td className="cifra px-3 py-2 text-right text-xs">
                    {monto(f.saldo_actual)}
                  </td>
                  <td className="cifra px-3 py-2 text-right text-xs text-tinta-suave">
                    {monto(f.saldo_comparativo)}
                  </td>
                  <td className={`cifra px-3 py-2 text-right ${
                    Number(f.variacion) < 0 ? "text-rojo" : ""
                  }`}>
                    {monto(f.variacion)}
                  </td>
                  <td className="cifra px-3 py-2 text-right text-xs text-tinta-suave">
                    {f.variacion_pct === null ? "—" : `${f.variacion_pct}%`}
                  </td>
                  <td className={`px-3 py-2 text-xs ${COLOR_MOTIVO[f.motivo] ?? "text-tinta-suave"}`}>
                    {f.motivo ?? "—"}
                  </td>
                </tr>
                {f.significativa && obs[f.cuenta] && (
                  <tr className="border-b border-regla-fina bg-papel-hondo">
                    <td colSpan={7} className="px-3 py-2 text-xs leading-relaxed">
                      <span className={obs[f.cuenta].verificado ? "text-verde" : "text-ambar"}>
                        {obs[f.cuenta].verificado ? "IA · cifras verificadas" : "IA · revisar cifra sin verificar"}
                      </span>
                      <span className="ml-2 text-tinta-media">{obs[f.cuenta].texto}</span>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <div className="text-xs leading-relaxed text-tinta-suave">
        <p>
          <strong className="text-tinta-media">Monto</strong> supera el umbral de
          ejecución · <strong className="text-tinta-media">Comportamiento</strong>{" "}
          varía más del {String(d.pct_variacion)}% con monto no trivial ·{" "}
          <strong className="text-tinta-media">Naturaleza</strong> saldo contrario
          al esperado para la cuenta.
        </p>
        <p className="mt-1">
          Las clases 1, 2 y 3 se comparan contra el cierre del año anterior; las
          clases 4 a 7, contra el mismo corte del año pasado.
        </p>
      </div>
    </div>
  );
}
