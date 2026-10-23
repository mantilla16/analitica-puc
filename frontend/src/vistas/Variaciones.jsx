import { Fragment, useEffect, useState } from "react";
import { api, monto, entero, fecha } from "../api";
import { Aviso, Punteo } from "../comp/Piezas";
import CompMov, { pctTexto } from "../comp/CompMov";

/** Convierte el desglose del residuo en el argumento redactado, con las
 * cuentas más grandes del grupo que sí importa (el que no llegó al umbral
 * pero tampoco es trivial). Punto de partida para la nota, no un sustituto
 * del juicio del auditor. */
function resumenAutomatico(d) {
  const g = d?.desglose_no_seleccionado;
  if (!g) return "";
  const partes = [
    `De ${monto(d.residuo_no_seleccionado)} en variaciones no seleccionadas, ` +
      `${monto(g.trivial.monto)} (${entero(g.trivial.cuentas)} cuentas) está ` +
      `por debajo del error trivial, y ${monto(g.cerca_del_umbral.monto)} ` +
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
  const [seccion, setSeccion] = useState("MARCADAS");
  const [evidencia, setEvidencia] = useState(null);
  const [error, setError] = useState(null);
  const [obs, setObs] = useState({});
  const [generando, setGenerando] = useState({});

  useEffect(() => { api.fases().then(setFases).catch(() => {}); }, []);

  // `rev` fuerza a recalcular el comparativo despues de excluir o restaurar
  // una cuenta: la exclusion cambia la seleccion y el residuo en el servidor.
  const [rev, setRev] = useState(0);
  useEffect(() => {
    api.variaciones(encargoId, fase)
      .then((r) => { setD(r); if (!fase && r.fase) setFase(r.fase); })
      .catch((e) => setError(e.message));
  }, [encargoId, fase, rev]);

  // Excluir es juicio del auditor y queda en el papel: sin motivo no se hace.
  async function excluir(prefijo, nombre) {
    const motivo = window.prompt(
      `Motivo para excluir ${prefijo}${nombre ? ` (${nombre})` : ""} del análisis.\n` +
      "Queda en el papel de trabajo (mínimo 10 caracteres):");
    if (motivo === null) return;
    try {
      setError(null);
      await api.excluirCuenta(encargoId, prefijo, motivo);
      setRev((n) => n + 1);
    } catch (e) { setError(e.message); }
  }

  async function restaurar(prefijo) {
    try {
      setError(null);
      await api.restaurarCuenta(encargoId, prefijo);
      setRev((n) => n + 1);
    } catch (e) { setError(e.message); }
  }

  const [prefijoNuevo, setPrefijoNuevo] = useState("");

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
      // El tamaño del lote y si se genera solo lo decide el servidor: no
      // es lo mismo un endpoint en la nube que un modelo en CPU.
      let tamLote = 5;
      let auto = true;
      try {
        const cfg = await api.iaConfig();
        if (cfg?.lote) tamLote = cfg.lote;
        if (cfg?.auto === false) auto = false;
      } catch { /* sin config, se usan los valores por defecto */ }
      if (!vivo) return;

      let guardadas = {};
      try {
        const r = await api.observacionesGuardadas(encargoId, d.fase);
        guardadas = Object.fromEntries(r.map((x) => [x.codigo_puc, x]));
      } catch { /* sin guardadas, se generan todas */ }
      if (!vivo) return;
      setObs(guardadas);

      if (!auto) return;   // se generan a pedido, con el botón de cada fila

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

  async function verEvidencia(codigo) {
    setEvidencia({ codigo, datos: null });
    try {
      setEvidencia({ codigo, datos: await api.evidenciaCuenta(encargoId, d.fase, codigo) });
    } catch (err) {
      setEvidencia({ codigo, datos: null, error: err.message });
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
    // Cargado sin promover es un caso distinto de no cargado, y el remedio
    // también: el archivo ya está, lo que falta es llevarlo al balance.
    if (d.sin_promover?.length) {
      return (
        <Aviso tono="error" titulo="Un balance quedó sin promover">
          {d.sin_promover.map((f) => nombres[f]).join(" y ")} está cargado pero
          ninguna de sus filas llegó al balance: se quedó en el archivo leído.
          Vuelva a la pestaña Archivos y súbalo de nuevo. No se calcula el
          comparativo mientras eso pase, porque los saldos que faltan entrarían
          como cero y toda variación saldría siendo el saldo del año anterior
          con el signo cambiado.
        </Aviso>
      );
    }
    return (
      <Aviso tono="info" titulo="Faltan balances para comparar">
        Cargue {d.faltan.map((f) => nombres[f]).join(" y ")} en la pestaña
        Archivos. El comparativo necesita los tres.
      </Aviso>
    );
  }

  // La columna solo existe si el servidor pudo comparar: sin el insumo, una
  // columna de guiones diría "sin cambio" cuando en realidad es "sin dato".
  const mov = d.movimientos_comparados;
  const hayMov = mov?.disponible === true;
  const nCols = hayMov ? 9 : 8;

  const filas =
    seccion === "TODAS" ? d.filas
    : seccion === "MARCADAS" ? d.filas.filter((f) => f.significativa)
    : d.filas.filter((f) => f.motivo === seccion);

  return (
    <div className="space-y-6">
      {/* ------------------------------------------------------- fases */}
      <div className="flex flex-wrap items-center gap-1 border-b border-regla pb-3">
        <span className="rotulo mr-2">Analizar bajo la fase</span>
        {fases.map((f) => (
          <button key={f.fase} onClick={() => setFase(f.fase)}
                  className={`pestana ${d.fase === f.fase ? "pestana-activa" : ""}`}>
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
          <p className="rotulo">{d.materialidad?.nombre ?? "Materialidad"} · global</p>
          <p className="cifra mt-1 text-lg">
            {d.materialidad?.global ? monto(d.materialidad.global) : "—"}
          </p>
        </div>
        <div>
          <p className="rotulo">Desempeño · umbral de monto</p>
          <p className="cifra mt-1 text-lg">
            {(d.materialidad?.desempeno?.valor ?? d.umbral) ? monto(d.materialidad?.desempeno?.valor ?? d.umbral) : "—"}
          </p>
          {d.materialidad?.desempeno?.pct != null && (
            <p className="text-xs text-tinta-suave">
              {pctTexto(d.materialidad.desempeno.pct)} de la global
            </p>
          )}
        </div>
        <div>
          <p className="rotulo">
            Error trivial {d.aplica_trivialidad === false ? "· desactivado" : ""}
          </p>
          <p className="cifra mt-1 text-lg">
            {d.aplica_trivialidad === false
              ? "—"
              : (d.materialidad?.trivial?.valor ?? d.trivialidad)
                ? monto(d.materialidad?.trivial?.valor ?? d.trivialidad) : "—"}
          </p>
          {d.aplica_trivialidad !== false && d.materialidad?.trivial?.pct != null && (
            <p className="text-xs text-tinta-suave">
              {pctTexto(d.materialidad.trivial.pct)} de la global
            </p>
          )}
        </div>
        <div>
          <p className="rotulo">
            Variación {d.aplica_variacion === false ? "· desactivada" : ""}
          </p>
          <p className="cifra mt-1 text-lg">
            {d.aplica_variacion === false ? "—" : `${String(d.pct_variacion)}%`}
          </p>
        </div>
        <button onClick={() => verHistorial(null)}
                className="rotulo ml-auto text-tinta-suave hover:text-tinta">
          Histórico de análisis
        </button>
      </div>

      {/* --------------------------------------------- secciones por motivo */}
      <div className="flex flex-wrap items-center gap-1 border-b border-regla pb-2">
        {[
          ["MARCADAS", "Para revisar", d.significativas],
          ["Monto", "Monto", d.por_motivo?.Monto],
          ["Comportamiento", "Comportamiento", d.por_motivo?.Comportamiento],
          ["Cuenta nueva", "Nuevas", d.por_motivo?.["Cuenta nueva"]],
          ["Cuenta cerrada", "Cerradas", d.por_motivo?.["Cuenta cerrada"]],
          ["Naturaleza", "Naturaleza", d.por_motivo?.Naturaleza],
          ["TODAS", "Todas", d.total_cuentas],
        ].map(([id, texto, n]) => (
          <button key={id} onClick={() => setSeccion(id)}
                  className={`pestana ${seccion === id ? "pestana-activa" : ""}`}>
            {texto}
            <span className="cifra ml-1.5 text-xs opacity-70">{entero(n ?? 0)}</span>
          </button>
        ))}
      </div>

      <details className="panel px-4 py-3 text-sm text-tinta-media">
        <summary className="cursor-pointer font-semibold text-tinta">
          Qué significa cada filtro
        </summary>
        <div className="mt-3 grid gap-x-8 gap-y-2 text-xs leading-relaxed sm:grid-cols-2">
          <p><strong className="text-tinta">Para revisar:</strong> todas las
          cuentas seleccionadas por alguno de los criterios siguientes.</p>
          <p><strong className="text-tinta">Monto:</strong> la variación absoluta
          alcanza o supera la materialidad de desempeño de la fase.</p>
          <p><strong className="text-tinta">Comportamiento:</strong> supera el
          porcentaje configurado y no es una variación trivial.</p>
          <p><strong className="text-tinta">Nuevas / Cerradas:</strong> pasan de
          cero a un saldo no trivial, o de un saldo no trivial a cero.</p>
          <p><strong className="text-tinta">Naturaleza:</strong> el saldo queda
          contrario a su comportamiento contable esperado y no es trivial.</p>
          <p><strong className="text-tinta">Todas:</strong> muestra el universo
          completo, incluidas las cuentas que no entraron al alcance.</p>
        </div>
      </details>

      {/* ---------------------------------------------- control de alcance */}
      {d.residuo_supera_umbral ? (
        <Aviso tono="alerta" titulo="El alcance puede quedar corto">
          Las variaciones no seleccionadas suman{" "}
          <span className="cifra">{monto(d.residuo_no_seleccionado)}</span>, por
          encima de la materialidad de desempeño. Conviene bajar el umbral o dejar
          constancia de por qué no.
        </Aviso>
      ) : (
        <p className="text-xs text-tinta-suave">
          Lo no seleccionado suma{" "}
          <span className="cifra">{monto(d.residuo_no_seleccionado)}</span>, por
          debajo de la materialidad de desempeño de esta fase.
        </p>
      )}

      {/* ------------------------------------------------ desglose del residuo */}
      {d.desglose_no_seleccionado && (
        <div className="grid grid-cols-1 gap-px bg-regla sm:grid-cols-2">
          <div className="bg-papel-alto p-4">
            <p className="rotulo">Bajo el error trivial</p>
            <p className="cifra mt-1 text-lg">
              {monto(d.desglose_no_seleccionado.trivial.monto)}
            </p>
            <p className="text-xs text-tinta-suave">
              {entero(d.desglose_no_seleccionado.trivial.cuentas)} cuentas ·
              no aporta al argumento
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
        <div className="panel p-4">
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
        <div className="panel p-4">
          <p className="rotulo mb-2">Nota de alcance</p>
          <p className="text-sm leading-relaxed">{resumenAutomatico(d)}</p>
        </div>
      )}

      {/* --------------------------------------------------------- tabla
          `table-fixed` es lo que mantiene la tabla dentro del contenedor:
          con ancho automático, el párrafo largo de la observación de IA
          ensancha toda la tabla y saca de vista las primeras columnas.
          El min-w deja que en pantallas angostas sí se pueda desplazar. */}
      <div className="overflow-x-auto panel">
        <table className="w-full min-w-[900px] table-fixed text-sm">
          {/* La columna Variación va en cuerpo más grande que las otras
              cifras, así que necesita más aire o se monta sobre el %. */}
          <colgroup>
            <col className="w-[8%]" />
            <col className="w-[16%]" />
            <col className="w-[14%]" />
            <col className="w-[14%]" />
            <col className="w-[16%]" />
            <col className="w-[8%]" />
            <col className="w-[12%]" />
            <col className="w-[10%]" />
            {hayMov && <col className="w-[8%]" />}
          </colgroup>
          <thead className="border-b border-regla bg-papel-hondo">
            <tr className="rotulo text-left">
              <th className="px-3 py-2 font-normal">Cuenta</th>
              <th className="px-3 py-2 font-normal">Nombre</th>
              <th className="px-3 py-2 text-right font-normal" title="Saldo en su naturaleza: positivo = del lado normal de la cuenta (D o C); negativo = del lado contrario. No es el signo del ERP.">Actual · nat.</th>
              <th className="px-3 py-2 text-right font-normal" title="Saldo en su naturaleza, igual que Actual.">Comparativo · nat.</th>
              <th className="px-3 py-2 text-right font-normal">Variación</th>
              <th className="px-3 py-2 text-right font-normal">%</th>
              <th className="px-3 py-2 font-normal">Motivo</th>
              <th className="px-3 py-2 font-normal">IA</th>
              {hayMov && (
                <th className="px-3 py-2 text-right font-normal"
                    title="Cambio del neto de movimientos (1-ene al corte) contra la misma ventana del año anterior">
                  Δ mov.
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {filas.length === 0 && (
              <tr>
                <td colSpan={nCols} className="px-3 py-10 text-center text-tinta-suave">
                  Ninguna cuenta quedó marcada para revisión. Quite el filtro para verlas todas.
                </td>
              </tr>
            )}
            {filas.map((f) => (
              <Fragment key={f.cuenta}>
                <tr className="border-b border-regla-fina hover:bg-papel-hondo">
                  <td className="cifra whitespace-nowrap px-3 py-2">
                    {f.cuenta}
                    {f.naturaleza && (
                      <span className="ml-1 text-xs text-tinta-suave"
                            title={f.naturaleza === "C" ? "Naturaleza crédito" : "Naturaleza débito"}>
                        {f.naturaleza}
                      </span>
                    )}
                  </td>
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
                    <div className="flex flex-col items-start gap-1">
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
                      <button onClick={() => verEvidencia(f.cuenta)}
                              className="rotulo text-tinta-suave hover:text-tinta">
                        Evidencia
                      </button>
                      <button onClick={() => excluir(f.cuenta, f.nombre)}
                              title="Sacar esta cuenta del análisis (pide motivo)"
                              className="rotulo text-tinta-suave hover:text-rojo">
                        Excluir
                      </button>
                    </div>
                  </td>
                  {hayMov && <CeldaDeltaMov c={mov.por_cuenta?.[f.cuenta]} />}
                </tr>
                {obs[f.cuenta] && (
                  <tr className="border-b border-regla-fina bg-papel-hondo">
                    <td colSpan={nCols} className="px-3 py-3">
                      {/* Una observacion escrita sobre otras cifras puede
                          afirmar lo contrario de lo que paso. Se avisa antes
                          del texto, no despues. */}
                      {obs[f.cuenta].desactualizada && (
                        <p className="mb-2 border-l-2 border-rojo bg-papel-alto px-3 py-2
                                      text-xs leading-relaxed text-rojo">
                          Esta observación se redactó con otras cifras y puede
                          decir lo contrario de lo que ocurrió. Vuelva a
                          generarla.
                          {obs[f.cuenta].cambiaron?.length > 0 && (
                            <span className="mt-1 block text-tinta-media">
                              {obs[f.cuenta].cambiaron.map((c) => (
                                <span key={c.cifra} className="mr-3">
                                  <span className="cifra">{c.cifra}</span>:{" "}
                                  {String(c.antes)} → {String(c.ahora)}
                                </span>
                              ))}
                            </span>
                          )}
                        </p>
                      )}

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
          <strong className="text-tinta-media">Monto</strong> supera la materialidad de
          desempeño · <strong className="text-tinta-media">Comportamiento</strong>{" "}
          varía más del {String(d.pct_variacion)}% con monto no trivial ·{" "}
          <strong className="text-tinta-media">Naturaleza</strong> saldo contrario
          al esperado para la cuenta.
        </p>
        <p className="mt-1">
          Las clases 1, 2 y 3 y las cuentas de orden (8 y 9) se comparan contra
          el cierre del año anterior; las clases 4 a 7, contra el mismo corte
          del año pasado.
        </p>
      </div>

      {/* ------------------------------------- exclusiones del auditor */}
      <section className="border-t border-regla pt-6">
        <p className="rotulo mb-1">Excluidas del análisis</p>
        <p className="mb-3 max-w-2xl text-xs text-tinta-suave">
          Cuentas que el auditor decidió no analizar. Siguen cargadas en el
          balance, pero no se seleccionan ni suman en lo no seleccionado. El
          papel de trabajo las declara con su motivo.
        </p>

        {(d.exclusiones ?? []).length > 0 ? (
          <div className="mb-4 border-t border-regla text-sm">
            {d.exclusiones.map((e) => {
              const cuentas = (d.excluidas ?? []).filter(
                (f) => f.exclusion?.prefijo === e.prefijo);
              return (
                <div key={e.prefijo}
                     className="flex flex-wrap items-baseline gap-3 border-b border-regla-fina py-2">
                  <span className="cifra w-16 font-medium">{e.prefijo}</span>
                  <span className="flex-1 text-xs text-tinta-media">
                    {e.motivo}
                    <span className="ml-2 text-tinta-suave">
                      · {cuentas.length} cuenta(s) ·{" "}
                      <span className="cifra">
                        {monto(cuentas.reduce((s, f) => s + Math.abs(Number(f.variacion)), 0))}
                      </span>{" "}
                      en variación · {e.excluido_por ?? "—"} · {fecha(e.excluido_en)}
                    </span>
                  </span>
                  <button onClick={() => restaurar(e.prefijo)}
                          className="rotulo text-tinta-suave hover:text-verde">
                    Restaurar
                  </button>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="mb-4 text-xs text-tinta-suave">Ninguna cuenta excluida.</p>
        )}

        {d.excluidas_superan_umbral && (
          <div className="mb-4">
            <Aviso tono="alerta" titulo="Lo excluido supera la materialidad de desempeño">
              Las variaciones de las cuentas excluidas suman{" "}
              <span className="cifra">{monto(d.variacion_excluida)}</span>. La
              decisión debe quedar soportada en el legajo.
            </Aviso>
          </div>
        )}

        {/* Para sacar una clase o grupo entero (p.ej. 9, cuentas de orden). */}
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <input value={prefijoNuevo}
                 onChange={(e) => setPrefijoNuevo(e.target.value.replace(/\D/g, "").slice(0, 4))}
                 placeholder="Clase, grupo o cuenta (ej. 9, 24, 2408)"
                 className="cifra w-72 border border-regla bg-papel px-3 py-2 text-sm" />
          <button onClick={async () => { await excluir(prefijoNuevo); setPrefijoNuevo(""); }}
                  disabled={!prefijoNuevo}
                  className="rotulo border border-regla px-3 py-2 hover:bg-papel disabled:opacity-40">
            Excluir
          </button>
        </div>
      </section>

      {historial && (
        <Historial h={historial} onCerrar={() => setHistorial(null)} />
      )}

      {evidencia && (
        <Evidencia e={evidencia} mov={mov} onCerrar={() => setEvidencia(null)} />
      )}
    </div>
  );
}

/** Δ del neto de movimientos de una cuenta contra el año anterior, con los
 *  dos netos en el tooltip. "—" cuando la cuenta no tiene base de comparación. */
function CeldaDeltaMov({ c }) {
  const n = c?.delta_neto_pct;
  const tip = c
    ? `Actual ${monto(c.actual?.neto ?? 0)} · año anterior ${monto(c.anterior?.neto ?? 0)} · Δ ${monto(c.delta_neto)}`
    : "Sin movimientos en ninguno de los dos periodos";
  return (
    <td title={tip}
        className={`cifra whitespace-nowrap px-3 py-2 text-right text-xs ${
          Number(n) < 0 ? "text-rojo" : "text-tinta-suave"}`}>
      {n === null || n === undefined ? "—" : pctTexto(n)}
    </td>
  );
}

/** Los datos crudos detrás de una cuenta. Existe para poder contrastar lo
 *  que afirma la IA contra lo que de verdad hay en los movimientos: el
 *  texto generado es un punto de partida, no evidencia. */
function Evidencia({ e, mov, onCerrar }) {
  const d = e.datos;
  // El servidor entrega la comparación para todas las cuentas en el
  // comparativo; se recorta a la de esta evidencia.
  const comp = mov
    ? { ...mov, cuenta: mov.por_cuenta?.[String(e.codigo).slice(0, 4)] ?? null }
    : d?.movimientos_vs_anterior;
  const c = d?.cuadre;

  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-tinta/25 backdrop-blur-[2px]" onClick={onCerrar}>
      <div
        className="deslizar h-full w-full max-w-3xl overflow-y-auto border-l border-regla bg-papel-alto p-6 shadow-[var(--sombra-alta)]"
        onClick={(ev) => ev.stopPropagation()}
      >
        <div className="mb-6 flex items-start justify-between">
          <div>
            <p className="rotulo">Evidencia</p>
            <p className="cifra mt-1 text-2xl">{e.codigo}</p>
            {d?.nombre && <p className="text-sm text-tinta-media">{d.nombre}</p>}
          </div>
          <button onClick={onCerrar} className="rotulo hover:text-tinta">Cerrar ✕</button>
        </div>

        {e.error && <Aviso tono="error">{e.error}</Aviso>}
        {!d && !e.error && <p className="text-sm text-tinta-suave">Cargando…</p>}

        {d?.listo && (
          <div className="space-y-8">
            {/* ------------------------------------------------ el cuadre */}
            {c ? (
              <div className={`border-l-2 p-4 ${c.cuadra
                ? "border-verde bg-verde-tenue" : "border-rojo bg-rojo-tenue"}`}>
                <p className="rotulo mb-2 flex items-center gap-2">
                  {c.cuadra && <Punteo tam={14} />}
                  {c.cuadra
                    ? `Los movimientos explican ${c.contra}`
                    : `Los movimientos NO explican ${c.contra}`}
                </p>
                <div className="space-y-1 text-sm">
                  <p>
                    <span className="text-tinta-suave">Débitos</span>{" "}
                    <span className="cifra">{c.debito}</span>
                    <span className="text-tinta-suave"> − créditos </span>
                    <span className="cifra">{c.credito}</span>
                    <span className="text-tinta-suave"> = neto </span>
                    <span className="cifra">{c.neto}</span>
                  </p>
                  <p>
                    <span className="text-tinta-suave">Contra {c.contra}: </span>
                    <span className="cifra">{c.esperado}</span>
                    <span className="text-tinta-suave"> · diferencia </span>
                    <span className={`cifra ${c.cuadra ? "" : "text-rojo"}`}>
                      {c.diferencia}
                    </span>
                  </p>
                  <p className="text-xs text-tinta-suave">
                    {Number(c.movimientos) === 0
                      ? "La cuenta no tiene movimientos en el archivo cargado."
                      : `${entero(c.movimientos)} movimientos del periodo.`}
                    {c.cuadra
                      ? (Number(c.movimientos) === 0
                          ? " Sin actividad y sin variación: es consistente."
                          : " La cifra se reconstruye con los movimientos cargados.")
                      : " Revise antes de sostener cualquier explicación sobre esta cuenta."}
                  </p>
                </div>
              </div>
            ) : (
              <Aviso tono="info">
                Sin movimientos cargados para esta cuenta: no hay contra qué
                contrastar la cifra. Cargue los movimientos del periodo en la
                pestaña Archivos.
              </Aviso>
            )}

            {/* ------------------------------ contra el año anterior */}
            <CompMov datos={comp} />

            {/* ------------------------------------------- por auxiliar */}
            {d.auxiliares?.length > 0 && (
              <section>
                <p className="rotulo mb-2">
                  Composición · {d.auxiliares.length} auxiliares
                </p>
                <div className="border-t border-regla">
                  {d.auxiliares.map((a) => (
                    <div key={a.codigo}
                         className="flex items-baseline gap-3 border-b border-regla-fina py-2 text-sm">
                      <span className="cifra w-24 shrink-0 text-xs">{a.codigo}</span>
                      <span className="min-w-0 flex-1 truncate" title={a.nombre}>
                        {a.nombre}
                      </span>
                      <span className="cifra shrink-0">{a.variacion}</span>
                      <span className="cifra w-16 shrink-0 text-right text-xs text-tinta-suave">
                        {a.pct_de_la_variacion_total ?? "—"}%
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* --------------------------------------------- patrones */}
            {d.patrones?.length > 0 && (
              <section>
                <p className="rotulo mb-2">
                  Qué se movió · agrupado por descripción
                </p>
                <div className="border-t border-regla">
                  {d.patrones.map((p, i) => (
                    <div key={i}
                         className="flex items-baseline gap-3 border-b border-regla-fina py-2 text-sm">
                      <span className="cifra w-10 shrink-0 text-xs text-tinta-suave">
                        {p.veces}×
                      </span>
                      <span className="min-w-0 flex-1 truncate" title={p.descripcion}>
                        {p.descripcion ?? "—"}
                      </span>
                      <span className="cifra shrink-0">{monto(p.neto)}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* ------------------------------------------ movimientos */}
            {d.movimientos?.length > 0 && (
              <section>
                <p className="rotulo mb-2">
                  Movimientos más grandes · {d.movimientos.length}
                </p>
                <div className="border-t border-regla">
                  {d.movimientos.map((m, i) => (
                    <div key={i} className="border-b border-regla-fina py-2 text-sm">
                      <div className="flex items-baseline gap-3">
                        <span className="cifra w-20 shrink-0 text-xs">{fecha(m.fecha)}</span>
                        <span className="cifra w-24 shrink-0 truncate text-xs">
                          {m.num_doc ?? "—"}
                        </span>
                        <span className="cifra w-24 shrink-0 text-xs text-tinta-suave">
                          {m.codigo_puc}
                        </span>
                        <span className="cifra ml-auto shrink-0">
                          {monto(Number(m.debito) - Number(m.credito))}
                        </span>
                      </div>
                      <p className="mt-0.5 truncate text-xs text-tinta-suave">
                        {m.tercero_nombre ? `${m.tercero_nombre} · ` : ""}
                        {m.descripcion}
                      </p>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-xs text-tinta-suave">
                  Se listan los de mayor magnitud. El cuadre de arriba sí
                  considera la totalidad de los movimientos de la cuenta.
                </p>
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** Repositorio de análisis del cliente: todas las versiones, de todos los
 *  encargos y fases. Nada se sobrescribe, así que acá queda el rastro
 *  completo de lo que redactó la IA y de los ajustes que pidió el auditor. */
function Historial({ h, onCerrar }) {
  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-tinta/25 backdrop-blur-[2px]" onClick={onCerrar}>
      <div
        className="deslizar h-full w-full max-w-2xl overflow-y-auto border-l border-regla bg-papel-alto p-6 shadow-[var(--sombra-alta)]"
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
