import { useEffect, useState } from "react";
import { api, monto, entero, fecha } from "../api";
import { Aviso, Boton, Chip, Punteo } from "../comp/Piezas";

const TONO_ESTADO = {
  OK: "verde", ALERTA: "ambar", FALLA: "rojo",
  BLOQUEANTE: "rojo", NO_EJECUTADO: "ambar",
};

const TONO_RIESGO = { BAJO: "verde", MEDIO: "cian", ALTO: "ambar", "MÁXIMO": "rojo" };

const TONO_CONCLUSION = {
  RAZONABLE: "verde",
  RAZONABLE_CON_SALVEDADES: "ambar",
  NO_CONCLUYENTE: "rojo",
};

function Seccion({ n, titulo, nota, children }) {
  return (
    <section className="mt-10">
      <div className="mb-3 flex items-baseline gap-3 border-b border-regla pb-2">
        <span className="cifra text-xs text-tinta-suave">{n}</span>
        <h2 className="text-lg font-semibold tracking-tight">{titulo}</h2>
      </div>
      {nota && <p className="mb-3 max-w-3xl text-xs leading-relaxed text-tinta-suave">{nota}</p>}
      {children}
    </section>
  );
}

/* Nombres legibles de los insumos, para no mostrar la constante interna
   en un documento que lee un tercero. */
const INSUMO = {
  BAL_ACTUAL: "Balance a la fecha de corte",
  BAL_CIERRE_ANTERIOR: "Balance al 31-dic del año anterior",
  BAL_CORTE_ANTERIOR: "Balance al mismo corte del año anterior",
};

/** Las cuentas concretas detrás de un control que falló. Sin esto el
 *  papel dice "falló" y deja al auditor buscando a ciegas dónde. */
function DetalleFalla({ c }) {
  // G02: descuadres de línea, agrupados por balance
  const porBalance = Object.entries(c.cifras ?? {})
    .filter(([, v]) => Array.isArray(v) && v.length && v[0]?.codigo);
  // G03: cuentas donde los movimientos no reproducen la cifra
  const noCuadran = c.cifras?.no_cuadran ?? [];

  if (!porBalance.length && !noCuadran.length) return null;

  return (
    <div className="mt-2 rounded-[8px] bg-rojo-tenue p-3">
      {porBalance.map(([tipo, filas]) => (
        <div key={tipo} className="mb-2 last:mb-0">
          <p className="rotulo text-rojo">{INSUMO[tipo] ?? tipo}</p>
          {filas.map((f) => (
            <p key={f.codigo} className="mt-1 flex flex-wrap items-baseline gap-2 text-xs">
              <span className="cifra font-semibold">{f.codigo}</span>
              <span className="text-tinta-media">{f.nombre}</span>
              <span className="cifra ml-auto text-rojo">{f.diferencia}</span>
            </p>
          ))}
        </div>
      ))}

      {noCuadran.map((f) => (
        <p key={f.cuenta} className="mt-1 text-xs">
          <span className="cifra font-semibold">{f.cuenta}</span>{" "}
          <span className="text-tinta-media">{f.nombre}</span>
          {" · "}
          <span className="text-tinta-suave">movimientos </span>
          <span className="cifra">{f.neto_movimientos}</span>
          <span className="text-tinta-suave"> contra {f.contra} </span>
          <span className="cifra">{f.esperado}</span>
          <span className="text-tinta-suave"> · diferencia </span>
          <span className="cifra text-rojo">{f.diferencia}</span>
        </p>
      ))}
    </div>
  );
}

/** Un control con su marca, su estado y contra qué se contrastó. */
function Control({ c }) {
  return (
    <div className="flex gap-3 border-b border-regla-fina py-3 last:border-0">
      <span className="cifra w-6 shrink-0 text-center text-lg">{c.marca}</span>
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
          <span className="cifra text-xs text-tinta-suave">{c.codigo}</span>
          {c.nombre}
          <Chip tono={TONO_ESTADO[c.estado] ?? "gris"}>{c.estado}</Chip>
          {!c.es_evidencia && <Chip tono="gris">no es evidencia</Chip>}
        </p>
        <p className="mt-1 text-xs leading-relaxed text-tinta-media">{c.detalle}</p>
        {c.estado === "FALLA" && <DetalleFalla c={c} />}
      </div>
    </div>
  );
}

/**
 * Papel de trabajo. Todo lo que se muestra viene calculado del servidor:
 * esta vista no suma ni decide nada, solo presenta y permite imprimir.
 */
export default function Papel({ encargoId, fase }) {
  const [p, setP] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setP(null);
    api.papel(encargoId, fase).then(setP).catch((e) => setError(e.detalle ?? e.message));
  }, [encargoId, fase]);

  if (error) return <Aviso tono="error">{String(error)}</Aviso>;
  if (!p) return (
    <p className="text-sm text-tinta-suave">
      Armando el papel… se está corriendo el cruce contra movimientos de cada
      cuenta seleccionada.
    </p>
  );
  if (!p.listo) return (
    <Aviso tono="info" titulo="No hay con qué armar el papel">{p.motivo}</Aviso>
  );

  const id = p.identificacion;
  const d = p.comparativo;
  const evidencia = p.gates.filter((g) => g.es_evidencia);
  const internos = p.gates.filter((g) => !g.es_evidencia);

  return (
    <div className="papel">
      {/* ------------------------------------------------------ portada */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b-2 border-marca pb-5">
        <div>
          <p className="rotulo">{id.norma}</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-marca">
            {id.papel}
          </h1>
          <p className="mt-1 text-sm text-tinta-media">
            {id.cliente} · <span className="cifra">{id.nit}</span>
          </p>
        </div>
        <div className="text-right text-xs text-tinta-suave">
          <p>Corte <span className="cifra text-tinta">{fecha(id.fecha_corte)}</span></p>
          <p className="mt-0.5">Fase <span className="text-tinta">{id.fase}</span></p>
          <p className="mt-0.5">Responsable <span className="text-tinta">{id.responsable ?? "—"}</span></p>
          <div className="no-imprimir mt-3 flex justify-end gap-2">
            <Boton onClick={() => api.papelExcel(encargoId, fase)}>
              Descargar Excel
            </Boton>
            <Boton variante="contorno" onClick={() => window.print()}>
              Imprimir / PDF
            </Boton>
          </div>
        </div>
      </div>

      {/* --------------------------------------------------- conclusión */}
      {/* Va primero a propósito: quien revisa quiere saber en qué terminó
          antes de recorrer cómo se llegó ahí. */}
      <div className={`mt-6 rounded-[12px] border-l-4 p-5 ${
        p.conclusion.estado === "RAZONABLE" ? "border-verde bg-verde-tenue"
        : p.conclusion.estado === "NO_CONCLUYENTE" ? "border-rojo bg-rojo-tenue"
        : "border-ambar bg-ambar-tenue"}`}>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="rotulo">Conclusión</span>
          <Chip tono={TONO_CONCLUSION[p.conclusion.estado] ?? "gris"}>
            {p.conclusion.estado.replaceAll("_", " ")}
          </Chip>
          <Chip tono={TONO_RIESGO[p.riesgo.nivel] ?? "gris"}>
            riesgo {p.riesgo.nivel}
          </Chip>
        </div>
        <p className="max-w-4xl text-sm leading-relaxed">{p.conclusion.texto}</p>
      </div>

      {/* --------------------------------------------- contrato de datos */}
      <Seccion n="1" titulo="Contrato de datos"
               nota="De qué archivo y de qué columna salió cada cifra. La huella
                     SHA-256 ata este papel a un archivo concreto: si el cliente
                     reenvía otro, la huella cambia y el papel deja de
                     corresponder a lo que se revisó.">
        <div className="space-y-2">
          {p.contrato_datos.map((c) => (
            <div key={c.tipo} className={`panel p-4 ${c.cargado ? "" : "panel-punteado"}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{c.insumo}</span>
                {!c.requerido && <Chip tono="gris">opcional</Chip>}
                {!c.cargado && <Chip tono={c.requerido ? "rojo" : "gris"}>sin cargar</Chip>}
                {c.cargado && <Chip tono="cian">{c.estado}</Chip>}
              </div>

              {c.cargado && (
                <>
                  <p className="mt-1 break-all text-xs text-tinta-media">{c.archivo}</p>
                  <div className="mt-2 grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
                    <p><span className="text-tinta-suave">Huella SHA-256: </span>
                      <span className="cifra break-all">{c.huella_sha256}</span></p>
                    <p><span className="text-tinta-suave">Hoja: </span>
                      {c.hoja ?? "—"}
                      {c.perfil_version && ` · perfil v${c.perfil_version}`}</p>
                    <p><span className="text-tinta-suave">Periodo: </span>
                      <span className="cifra">{fecha(c.periodo.inicio)} a {fecha(c.periodo.fin)}</span></p>
                    <p><span className="text-tinta-suave">Filas: </span>
                      <span className="cifra">{entero(c.filas_leidas)}</span> leídas ·{" "}
                      <span className="cifra">{entero(c.filas_promovidas)}</span> promovidas</p>
                    <p><span className="text-tinta-suave">Cargado por: </span>
                      {c.subido_por ?? "—"} el {fecha(c.fecha_carga)}</p>
                  </div>

                  {Object.keys(c.columnas).length > 0 && (
                    <div className="mt-3 border-t border-regla-fina pt-2">
                      <p className="rotulo mb-1">Origen de cada campo</p>
                      <div className="grid gap-x-6 text-xs sm:grid-cols-2">
                        {Object.entries(c.columnas).map(([campo, col]) => (
                          <p key={campo}>
                            <span className="cifra text-tinta-suave">{campo}</span>
                            {" ← "}
                            <span className="text-tinta-media">{col}</span>
                          </p>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      </Seccion>

      {/* ------------------------------------------- controles previos */}
      <Seccion n="2" titulo="Controles de integridad previos al cruce"
               nota="Comparar balances de entidades, periodos o monedas distintas
                     produce un número perfectamente formado y completamente falso.
                     Estos controles corren antes de calcular nada.">
        <div className="panel px-5 py-1">
          {p.controles_previos.map((c) => <Control key={c.codigo} c={c} />)}
        </div>
      </Seccion>

      {/* ----------------------------------------- cédula sumaria */}
      <Seccion n="3" titulo="Cédula sumaria — saldos por clase"
               nota="Saldo en naturaleza al corte, a nivel de cuenta.">
        <div className="panel tabla overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="rotulo border-b border-regla text-left">
                <th className="px-3 py-2 font-normal">Clase</th>
                <th className="px-3 py-2 font-normal">Nombre</th>
                <th className="px-3 py-2 text-right font-normal">Cuentas</th>
                <th className="px-3 py-2 text-right font-normal">Saldo</th>
              </tr>
            </thead>
            <tbody>
              {p.cedula_sumaria.map((c) => (
                <tr key={c.clase} className="border-b border-regla-fina">
                  <td className="cifra px-3 py-2">{c.clase}</td>
                  <td className="px-3 py-2">{c.clase_nombre}</td>
                  <td className="cifra px-3 py-2 text-right text-xs">{entero(c.cuentas)}</td>
                  <td className="cifra px-3 py-2 text-right">{monto(c.saldo)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Seccion>

      {/* --------------------------------------------------- controles */}
      <Seccion n="4" titulo="Controles ejecutados"
               nota="Un control solo es evidencia si puede fallar y si contrasta
                     contra algo que no se derive de lo que está verificando.">
        <p className="rotulo mb-2">Constituyen evidencia</p>
        <div className="panel px-5 py-1">
          {evidencia.map((g) => <Control key={g.codigo} c={g} />)}
        </div>

        {internos.length > 0 && (
          <>
            <p className="rotulo mb-2 mt-5">Consistencia interna — no constituyen evidencia</p>
            <div className="panel-plano px-5 py-1 opacity-80">
              {internos.map((g) => <Control key={g.codigo} c={g} />)}
            </div>
          </>
        )}
      </Seccion>

      {/* -------------------------------------------- alcance y selección */}
      <Seccion n="5" titulo="Alcance y selección"
               nota="La materialidad y los criterios que definieron qué cuentas
                     entran a revisión.">
        <div className="grid gap-3 sm:grid-cols-4">
          {[
            ["Materialidad de la fase", d.umbral ? monto(d.umbral) : "sin aplicar"],
            ["Cuentas comparadas", entero(d.total_cuentas)],
            ["Seleccionadas", entero(d.significativas)],
            ["No seleccionadas (suma)", monto(d.residuo_no_seleccionado)],
          ].map(([r, v]) => (
            <div key={r} className="panel p-4">
              <p className="rotulo">{r}</p>
              <p className="cifra mt-1 text-lg">{v}</p>
            </div>
          ))}
        </div>

        <p className="mt-3 text-xs leading-relaxed text-tinta-media">
          Criterios vigentes: monto contra materialidad
          {d.aplica_variacion !== false
            ? `, variación porcentual desde ${String(d.pct_variacion)}%`
            : ", variación porcentual desactivada"}
          {d.aplica_trivialidad !== false
            ? `, piso de ruido en ${String(d.pct_trivialidad)}% de la materialidad`
            : ", sin piso de ruido"}
          , más los criterios estructurales de cuenta nueva, cuenta cerrada y
          naturaleza invertida.
        </p>

        {d.residuo_supera_umbral && (
          <div className="mt-3">
            <Aviso tono="alerta" titulo="El alcance puede quedar corto">
              Las variaciones no seleccionadas suman{" "}
              <span className="cifra">{monto(d.residuo_no_seleccionado)}</span>, por
              encima de la materialidad de la fase.
            </Aviso>
          </div>
        )}

        <p className="rotulo mb-2 mt-5">Cuentas seleccionadas</p>
        <div className="panel tabla overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="rotulo border-b border-regla text-left">
                <th className="px-3 py-2 font-normal">Cuenta</th>
                <th className="px-3 py-2 font-normal">Nombre</th>
                <th className="px-3 py-2 text-right font-normal">Actual</th>
                <th className="px-3 py-2 text-right font-normal">Comparativo</th>
                <th className="px-3 py-2 text-right font-normal">Variación</th>
                <th className="px-3 py-2 text-right font-normal">%</th>
                <th className="px-3 py-2 font-normal">Motivo</th>
                <th className="px-3 py-2 text-center font-normal">Marca</th>
              </tr>
            </thead>
            <tbody>
              {d.filas.filter((f) => f.significativa).map((f) => (
                <tr key={f.cuenta} className="border-b border-regla-fina">
                  <td className="cifra px-3 py-2">{f.cuenta}</td>
                  <td className="max-w-[12rem] truncate px-3 py-2" title={f.nombre}>{f.nombre}</td>
                  <td className="cifra whitespace-nowrap px-3 py-2 text-right text-xs">{monto(f.saldo_actual)}</td>
                  <td className="cifra whitespace-nowrap px-3 py-2 text-right text-xs text-tinta-suave">{monto(f.saldo_comparativo)}</td>
                  <td className="cifra whitespace-nowrap px-3 py-2 text-right">{monto(f.variacion)}</td>
                  <td className="cifra px-3 py-2 text-right text-xs text-tinta-suave">
                    {f.variacion_pct === null ? "—" : `${f.variacion_pct}%`}
                  </td>
                  <td className="px-3 py-2 text-xs">{f.motivo}</td>
                  <td className="cifra px-3 py-2 text-center">Δ</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Seccion>

      {/* --------------------------------------------------- hallazgos */}
      <Seccion n="6" titulo="Hallazgos"
               nota="Lo que el sistema detectó durante la carga y validación.
                     Los no explicados no se fuerzan a cuadrar.">
        {p.hallazgos.length === 0 ? (
          <div className="panel flex items-center gap-3 p-5">
            <Punteo tam={16} />
            <p className="text-sm text-tinta-media">
              No se registraron hallazgos en la carga ni en la validación de este encargo.
            </p>
          </div>
        ) : (
          <div className="panel px-5 py-1">
            {p.hallazgos.map((h) => (
              <div key={h.id} className="flex gap-3 border-b border-regla-fina py-3 last:border-0">
                <Chip tono={h.severidad === "BLOQUEANTE" ? "rojo" : "ambar"}>
                  {h.severidad}
                </Chip>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold">
                    {h.tipo}
                    {h.codigo_puc && <span className="cifra ml-2 text-xs">{h.codigo_puc}</span>}
                  </p>
                  <p className="text-xs text-tinta-media">{h.descripcion}</p>
                </div>
                {h.monto != null && (
                  <span className="cifra shrink-0 text-sm">{monto(h.monto)}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </Seccion>

      {/* --------------------------------------------- índice de riesgo */}
      <Seccion n="7" titulo="Índice de riesgo"
               nota="Cada punto declara de dónde sale. No se generaliza: un
                     descuadre no pesa lo mismo que una moneda sin declarar.">
        <div className="panel p-5">
          <div className="mb-3 flex items-baseline gap-3">
            <span className="cifra text-3xl">{p.riesgo.puntos}</span>
            <Chip tono={TONO_RIESGO[p.riesgo.nivel] ?? "gris"}>{p.riesgo.nivel}</Chip>
          </div>
          {p.riesgo.detalle.length === 0 ? (
            <p className="text-sm text-tinta-media">
              Ningún control aportó puntos de riesgo.
            </p>
          ) : (
            <div className="border-t border-regla-fina">
              {p.riesgo.detalle.map((r, i) => (
                <div key={i} className="flex items-baseline gap-3 border-b border-regla-fina py-2 text-sm last:border-0">
                  <span className="cifra w-6 shrink-0 text-right">{r.puntos}</span>
                  <span className="flex-1">{r.motivo}</span>
                  <span className="rotulo shrink-0">{r.origen}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </Seccion>

      {/* ---------------------------------------------------- marcas */}
      <Seccion n="8" titulo="Marcas de auditoría"
               nota="Una marca sin leyenda es un símbolo, no evidencia (NIA 230).
                     Cada una declara qué se hizo y contra qué se contrastó.">
        <div className="panel px-5 py-1">
          {p.marcas.map((m) => (
            <div key={m.marca} className="flex gap-4 border-b border-regla-fina py-3 last:border-0">
              <span className="cifra w-6 shrink-0 text-center text-lg">{m.marca}</span>
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                  {m.nombre}
                  {m.nia !== "—" && <Chip tono="gris">{m.nia}</Chip>}
                  {!m.evidencia && <Chip tono="gris">no es evidencia</Chip>}
                </p>
                <p className="mt-0.5 text-xs text-tinta-media">{m.procedimiento}</p>
                <p className="mt-0.5 text-xs text-tinta-suave">
                  <span className="rotulo">Contra: </span>{m.contra}
                </p>
              </div>
            </div>
          ))}
        </div>
      </Seccion>

      {/* ---------------------------------------------- trazabilidad */}
      <Seccion n="9" titulo="Trazabilidad"
               nota="Si una cifra del papel no se rastrea hasta un evento
                     registrado, el papel no es auditable.">
        <div className="panel tabla overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="rotulo border-b border-regla text-left">
                <th className="px-3 py-2 font-normal">Fecha y hora</th>
                <th className="px-3 py-2 font-normal">Usuario</th>
                <th className="px-3 py-2 font-normal">Acción</th>
                <th className="px-3 py-2 font-normal">Origen</th>
              </tr>
            </thead>
            <tbody>
              {p.trazabilidad.eventos.slice(0, 60).map((e) => (
                <tr key={e.id} className="border-b border-regla-fina">
                  <td className="cifra whitespace-nowrap px-3 py-2 text-xs">
                    {new Date(e.creado_en).toLocaleString("es-CO")}
                  </td>
                  <td className="px-3 py-2 text-xs">{e.usuario ?? "—"}</td>
                  <td className="px-3 py-2 text-xs">
                    <Chip tono={e.exito ? "cian" : "rojo"}>{e.accion}</Chip>
                  </td>
                  <td className="cifra px-3 py-2 text-xs text-tinta-suave">{e.ip ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {p.trazabilidad.eventos.length > 60 && (
          <p className="mt-2 text-xs text-tinta-suave">
            Se muestran los 60 eventos más recientes de {entero(p.trazabilidad.eventos.length)}.
            El rastro completo está en la bitácora.
          </p>
        )}
      </Seccion>

      <p className="mt-10 border-t border-regla pt-4 text-xs leading-relaxed text-tinta-suave">
        Papel generado por Analítica PUC v{p.version} el{" "}
        {new Date().toLocaleString("es-CO")}. Las cifras provienen del motor
        determinístico; la aplicación no las recalcula al mostrarlas. Las
        observaciones redactadas con asistencia de IA se identifican como tales
        en la pestaña Variaciones y llevan su propia verificación de cifras.
      </p>
    </div>
  );
}
