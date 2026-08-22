import { Fragment, useEffect, useState } from "react";
import { api, monto, entero, fecha } from "../api";
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
  const [generando, setGenerando] = useState({});

  useEffect(() => { api.fases().then(setFases).catch(() => {}); }, []);

  useEffect(() => {
    api.variaciones(encargoId, fase)
      .then((r) => { setD(r); if (!fase && r.fase) setFase(r.fase); })
      .catch((e) => setError(e.message));
  }, [encargoId, fase]);

  const [progreso, setProgreso] = useState(null);   // {hecho, total} mientras corren los lotes
  const [ajuste, setAjuste] = useState({});         // {codigo: texto que escribe el auditor}
  const [historial, setHistorial] = useState(null); // panel lateral

  useEffect(() => { setObs({}); setProgreso(null); setAjuste({}); }, [encargoId, d?.fase]);

  /* Primero se pinta lo que ya está guardado; solo se manda a generar lo
     que falta. Recargar la página no vuelve a pagar el análisis completo. */
  useEffect(() => {
    if (!d?.listo || !d.aplica) return;
    let vivo = true;

    (async () => {
      // El tamaño del lote lo decide el servidor: 5 contra un endpoint en
      // la nube, menos contra un Ollama en CPU.
      let tamLote = 5;
      try {
        const cfg = await api.iaConfig();
        if (cfg?.lote) tamLote = cfg.lote;
      } catch { /* sin config, se usa el valor por defecto */ }
      if (!vivo) return;

      let guardadas = {};
      try {
        const r = await api.observacionesGuardadas(encargoId, d.fase);
        guardadas = Object.fromEntries(r.map((x) => [x.codigo_puc, x]));
      } catch { /* sin guardadas, se generan todas */ }
      if (!vivo) return;
      setObs(guardadas);

      const faltan = d.filas
        .filter((f) => f.significativa && !guardadas[f.cuenta])
        .map((f) => f.cuenta);
      if (!faltan.length) return;

      for (let i = 0; i < faltan.length; i += tamLote) {
        if (!vivo) return;
        const lote = faltan.slice(i, i + tamLote);
        setProgreso({ hecho: i, total: faltan.length });
        setGenerando((g) => ({ ...g, ...Object.fromEntries(lote.map((c) => [c, true])) }));
        try {
          const r = await api.observacionesLote(encargoId, d.fase, lote);
          if (!vivo) return;
          setObs((o) => ({ ...o, ...Object.fromEntries(r.map((x) => [x.codigo_puc, x])) }));
        } catch (err) {
          if (!vivo) return;
          setObs((o) => ({
            ...o,
            ...Object.fromEntries(lote.map((c) => [c, { texto: err.message, verificado: false }])),
          }));
        } finally {
          setGenerando((g) => ({ ...g, ...Object.fromEntries(lote.map((c) => [c, false])) }));
        }
      }
      if (vivo) setProgreso(null);
    })();

    return () => { vivo = false; };
  }, [encargoId, d?.fase, d?.listo, d?.aplica]);

  async function explicar(codigo, instruccion = null) {
    setGenerando((g) => ({ ...g, [codigo]: true }));
    try {
      const r = await api.observacionCuenta(encargoId, d.fase, codigo, instruccion);
      setObs((o) => ({ ...o, [codigo]: r }));
      setAjuste((a) => ({ ...a, [codigo]: "" }));
    } catch (err) {
      setObs((o) => ({ ...o, [codigo]: { texto: err.message, verificado: false } }));
    } finally {
      setGenerando((g) => ({ ...g, [codigo]: false }));
    }
  }

  async function verHistorial(codigo = null) {
    setHistorial({ codigo, filas: null });
    try {
      const filas = await api.historiaObservaciones(encargoId, codigo);
      setHistorial({ codigo, filas });
    } catch (err) {
      setHistorial({ codigo, filas: [], error: err.message });
    }
  }

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
        <button onClick={() => verHistorial(null)}
                className="rotulo text-tinta-suave hover:text-tinta">
          Histórico de análisis
        </button>
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

      {progreso && (
        <p className="text-xs text-tinta-suave">
          Generando observaciones con IA — {entero(progreso.hecho)} de{" "}
          {entero(progreso.total)}…
        </p>
      )}

      {/* -------------------------------------------------- nota de alcance */}
      {d.desglose_no_seleccionado && (
        <div className="border border-regla bg-papel-alto p-4">
          <p className="rotulo mb-2">Nota de alcance</p>
          <p className="text-sm leading-relaxed">{resumenAutomatico(d)}</p>
        </div>
      )}

      {/* --------------------------------------------------------- tabla
          `table-fixed` es lo que mantiene la tabla dentro del contenedor:
          con ancho automático, el párrafo largo de la observación de IA
          ensancha toda la tabla y saca de vista las primeras columnas.
          El min-w deja que en pantallas angostas sí se pueda desplazar. */}
      <div className="overflow-x-auto border border-regla bg-papel-alto">
        <table className="w-full min-w-[900px] table-fixed text-sm">
          <colgroup>
            <col className="w-[8%]" />
            <col className="w-[21%]" />
            <col className="w-[14%]" />
            <col className="w-[14%]" />
            <col className="w-[14%]" />
            <col className="w-[7%]" />
            <col className="w-[12%]" />
            <col className="w-[10%]" />
          </colgroup>
          <thead className="border-b border-regla bg-papel-hondo">
            <tr className="rotulo text-left">
              <th className="px-3 py-2 font-normal">Cuenta</th>
              <th className="px-3 py-2 font-normal">Nombre</th>
              <th className="px-3 py-2 text-right font-normal">Actual</th>
              <th className="px-3 py-2 text-right font-normal">Comparativo</th>
              <th className="px-3 py-2 text-right font-normal">Variación</th>
              <th className="px-3 py-2 text-right font-normal">%</th>
              <th className="px-3 py-2 font-normal">Motivo</th>
              <th className="px-3 py-2 font-normal">IA</th>
            </tr>
          </thead>
          <tbody>
            {filas.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-10 text-center text-tinta-suave">
                  Ninguna cuenta supera el umbral. Quite el filtro para ver todas.
                </td>
              </tr>
            )}
            {filas.map((f) => (
              <Fragment key={f.cuenta}>
                <tr className="border-b border-regla-fina hover:bg-papel-hondo">
                  <td className="cifra whitespace-nowrap px-3 py-2">{f.cuenta}</td>
                  <td className="truncate px-3 py-2" title={f.nombre}>
                    {f.nombre ?? "—"}
                  </td>
                  <td className="cifra whitespace-nowrap px-3 py-2 text-right text-xs">
                    {monto(f.saldo_actual)}
                  </td>
                  <td className="cifra whitespace-nowrap px-3 py-2 text-right text-xs text-tinta-suave">
                    {monto(f.saldo_comparativo)}
                  </td>
                  <td className={`cifra whitespace-nowrap px-3 py-2 text-right ${
                    Number(f.variacion) < 0 ? "text-rojo" : ""
                  }`}>
                    {monto(f.variacion)}
                  </td>
                  <td className="cifra whitespace-nowrap px-3 py-2 text-right text-xs text-tinta-suave">
                    {f.variacion_pct === null ? "—" : `${f.variacion_pct}%`}
                  </td>
                  <td className={`px-3 py-2 text-xs ${COLOR_MOTIVO[f.motivo] ?? "text-tinta-suave"}`}>
                    {f.motivo ?? "—"}
                  </td>
                  <td className="px-3 py-2">
                    {/* Sin `version` no hay análisis guardado: o nunca se
                        generó, o el intento falló y hay que reintentar. */}
                    {f.significativa && !obs[f.cuenta]?.version && (
                      <button
                        onClick={() => explicar(f.cuenta)}
                        disabled={generando[f.cuenta]}
                        className="rotulo text-tinta-suave hover:text-verde disabled:opacity-40"
                      >
                        {generando[f.cuenta]
                          ? "Generando…"
                          : obs[f.cuenta] ? "Reintentar" : "Explicar"}
                      </button>
                    )}
                  </td>
                </tr>
                {obs[f.cuenta] && (
                  <tr className="border-b border-regla-fina bg-papel-hondo">
                    <td colSpan={8} className="px-3 py-3">
                      <div className="flex items-baseline gap-2">
                        <span className={obs[f.cuenta].verificado ? "rotulo text-verde" : "rotulo text-ambar"}>
                          {obs[f.cuenta].verificado ? "IA · cifras verificadas" : "IA · revisar cifra sin verificar"}
                        </span>
                        {obs[f.cuenta].version && (
                          <span className="rotulo text-tinta-suave">
                            v{obs[f.cuenta].version}
                            {obs[f.cuenta].creado_en && ` · ${fecha(obs[f.cuenta].creado_en)}`}
                          </span>
                        )}
                        <button
                          onClick={() => verHistorial(f.cuenta)}
                          className="rotulo ml-auto text-tinta-suave hover:text-tinta"
                        >
                          Versiones
                        </button>
                      </div>

                      <p className="mt-1 break-words text-xs leading-relaxed text-tinta-media">
                        {obs[f.cuenta].texto}
                      </p>

                      {obs[f.cuenta].instruccion_auditor && (
                        <p className="mt-1 text-xs italic text-tinta-suave">
                          Ajustada con: “{obs[f.cuenta].instruccion_auditor}”
                        </p>
                      )}

                      <div className="mt-2 flex gap-2">
                        <input
                          value={ajuste[f.cuenta] ?? ""}
                          onChange={(e) => setAjuste((a) => ({ ...a, [f.cuenta]: e.target.value }))}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && ajuste[f.cuenta]?.trim()) {
                              explicar(f.cuenta, ajuste[f.cuenta].trim());
                            }
                          }}
                          placeholder="Pídele un ajuste: más breve, enfócate en el auxiliar X, menciona el riesgo…"
                          className="flex-1 border border-regla bg-papel px-2 py-1 text-xs"
                        />
                        <button
                          onClick={() => explicar(f.cuenta, ajuste[f.cuenta].trim())}
                          disabled={generando[f.cuenta] || !ajuste[f.cuenta]?.trim()}
                          className="rotulo border border-regla px-2 py-1 hover:bg-papel disabled:opacity-40"
                        >
                          {generando[f.cuenta] ? "Ajustando…" : "Ajustar"}
                        </button>
                      </div>
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

      {historial && (
        <Historial h={historial} onCerrar={() => setHistorial(null)} />
      )}
    </div>
  );
}

/** Repositorio de análisis del cliente: todas las versiones, de todos los
 *  encargos y fases. Nada se sobrescribe, así que acá queda el rastro
 *  completo de lo que redactó la IA y de los ajustes que pidió el auditor. */
function Historial({ h, onCerrar }) {
  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-tinta/20" onClick={onCerrar}>
      <div
        className="h-full w-full max-w-2xl overflow-y-auto border-l border-regla bg-papel p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-6 flex items-start justify-between">
          <div>
            <p className="rotulo">Histórico de análisis de IA</p>
            <p className="mt-1 text-sm text-tinta-media">
              {h.codigo ? `Cuenta ${h.codigo}` : "Todas las cuentas de este cliente"}
            </p>
          </div>
          <button onClick={onCerrar} className="rotulo hover:text-tinta">Cerrar ✕</button>
        </div>

        {h.error && <Aviso tono="error">{h.error}</Aviso>}
        {h.filas === null && (
          <p className="text-sm text-tinta-suave">Cargando…</p>
        )}
        {h.filas?.length === 0 && (
          <p className="text-sm text-tinta-suave">
            Todavía no hay análisis guardados para este cliente.
          </p>
        )}

        <div className="border-t border-regla">
          {(h.filas ?? []).map((o) => (
            <div key={o.id} className="border-b border-regla-fina py-3">
              <div className="flex items-baseline gap-2">
                <span className="cifra text-sm">{o.codigo_puc}</span>
                <span className="rotulo text-tinta-suave">v{o.version}</span>
                <span className={`rotulo ${o.verificado ? "text-verde" : "text-ambar"}`}>
                  {o.verificado ? "verificada" : "sin verificar"}
                </span>
                <span className="rotulo ml-auto text-tinta-suave">
                  {fecha(o.creado_en)}
                  {o.fecha_corte && ` · corte ${fecha(o.fecha_corte)}`}
                </span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-tinta-media">{o.texto}</p>
              {o.instruccion_auditor && (
                <p className="mt-1 text-xs italic text-tinta-suave">
                  Ajuste pedido: “{o.instruccion_auditor}”
                </p>
              )}
              <p className="mt-1 text-xs text-tinta-suave">
                {o.fase}
                {o.modelo && ` · ${o.modelo}`}
                {o.creado_por && ` · ${o.creado_por}`}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
