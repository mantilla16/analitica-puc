import { useCallback, useEffect, useState } from "react";
import { api, monto, entero, fecha, periodoDe, COMPARATIVO } from "../api";
import { Aviso, Boton, Chip, Cuadre, Dato, Punteo } from "../comp/Piezas";
import Mapeo from "./Mapeo";
import Balance from "./Balance";
import Variaciones from "./Variaciones";
import Materialidad from "./Materialidad";

const PESTANAS = [
  ["archivos", "Archivos"],
  ["materialidad", "Materialidad"],
  ["balance", "Balance"],
  ["variaciones", "Variaciones"],
];

export default function Encargo({ encargoId, onVolver }) {
  const [enc, setEnc] = useState(null);
  const [items, setItems] = useState([]);
  const [activo, setActivo] = useState(null);      // tipo de insumo abierto
  const [carga, setCarga] = useState(null);        // {id, requiere_mapeo}
  const [resultado, setResultado] = useState(null);
  const [evidencia, setEvidencia] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const [pestana, setPestana] = useState("archivos");

  const refrescar = useCallback(async () => {
    setEnc(await api.encargo(encargoId));
    setItems(await api.checklist(encargoId));
  }, [encargoId]);

  useEffect(() => { refrescar().catch((e) => setError(e.message)); }, [refrescar]);

  if (!enc) return <p className="p-12 text-sm text-tinta-suave">Cargando…</p>;

  const mats = enc.materialidades ?? [];
  const activa = mats.find((m) => m.fase === enc.fase_activa);

  async function subir(tipo, archivo) {
    setError(null); setResultado(null); setEvidencia(null); setOcupado(true);
    try {
      const p = periodoDe(tipo, enc);
      const fd = new FormData();
      fd.append("tipo", tipo);
      fd.append("archivo", archivo);
      fd.append("periodo_ini", p.ini);
      fd.append("periodo_fin", p.fin);
      // Quién sube el archivo lo toma el backend de la sesión, no de aquí.
      const r = await api.subir(encargoId, fd);
      setCarga(r);
      setActivo(tipo);
      if (!r.requiere_mapeo) await procesar(r.carga_id);
    } catch (e) { setError(e.message); }
    finally { setOcupado(false); }
  }

  async function procesar(cargaId) {
    setOcupado(true);
    try {
      const r = await api.procesar(cargaId);
      let promo = null;
      if (r.resultado !== "ARCHIVO_IDENTICO" && r.resultado !== "SIN_FILAS_NUEVAS") {
        const c = await api.carga(cargaId);
        if (c.tipo.startsWith("BAL")) promo = await api.promover(cargaId);
      }
      setResultado({ ...r, promocion: promo, carga_id: cargaId });
      await refrescar();
    } catch (e) { setError(e.message); }
    finally { setOcupado(false); }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <button onClick={onVolver} className="rotulo mb-8 hover:text-tinta">
        ← Encargos
      </button>

      {/* ---------------------------------------------------- encabezado */}
      <header className="border-b border-regla pb-6">
        <p className="rotulo">{enc.nit}</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{enc.razon_social}</h1>

        <div className="mt-6 grid grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-4">
          <Dato etiqueta="Corte">
            <span className="cifra">{fecha(enc.fecha_corte)}</span>
          </Dato>
          <Dato etiqueta="Clases 1 · 2 · 3 contra">
            <span className="cifra">{fecha(enc.fecha_cierre_anterior)}</span>
          </Dato>
          <Dato etiqueta="Clases 4 · 5 · 6 · 7 contra">
            <span className="cifra">{fecha(enc.fecha_corte_anterior)}</span>
          </Dato>
          <Dato etiqueta={activa ? activa.nombre : "Materialidad"}>
            {activa?.aplicar && activa?.valor ? (
              <span className="cifra">{monto(activa.valor)}</span>
            ) : (
              <button onClick={() => setPestana("materialidad")}
                      className="text-sm text-ambar underline underline-offset-4">
                sin definir
              </button>
            )}
          </Dato>
        </div>

        <p className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-tinta-suave">
          {mats.map((m) => (
            <span key={m.fase} className={m.fase === enc.fase_activa ? "text-tinta-media" : ""}>
              {m.fase_nombre}:{" "}
              <span className="cifra">{m.valor ? monto(m.valor) : "—"}</span>
              {!m.aplicar && m.valor ? " (sin aplicar)" : ""}
            </span>
          ))}
        </p>
      </header>

      {error && <div className="mt-6"><Aviso tono="error">{error}</Aviso></div>}

      {/* ----------------------------------------------------- pestañas */}
      <nav className="mt-8 flex flex-wrap gap-1 rounded-full bg-papel-hondo p-1">
        {PESTANAS.map(([id, texto]) => (
          <button
            key={id}
            onClick={() => setPestana(id)}
            className={`pestana ${pestana === id ? "pestana-activa" : ""}`}
          >
            {texto}
          </button>
        ))}
      </nav>

      {pestana === "materialidad" && (
        <div className="mt-8">
          <Materialidad encargoId={encargoId} onCambio={refrescar} />
        </div>
      )}
      {pestana === "balance" && (
        <div className="mt-8"><Balance encargoId={encargoId} /></div>
      )}
      {pestana === "variaciones" && (
        <div className="mt-8"><Variaciones encargoId={encargoId} /></div>
      )}

      {pestana === "archivos" && (<>
      {/* ------------------------------------------------------ insumos */}
      <section className="mt-8">
        <p className="rotulo mb-3">Archivos del cliente</p>
        <div className="space-y-2">
          {items.map((i) => (
            <div key={i.tipo}
                 className={`panel tarjeta-activa flex items-center gap-4 px-4 py-3.5 ${
                   i.cargado ? "" : "panel-punteado"}`}>
              <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                i.cargado ? "bg-verde-tenue" : "bg-papel-hondo"}`}>
                {i.cargado ? <Punteo tam={16} /> : (
                  <span className="block h-2 w-2 rounded-full bg-tinta-suave/40" />
                )}
              </span>

              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-sm font-semibold">
                  {i.insumo}
                  {!i.requerido && <Chip tono="gris">opcional</Chip>}
                </p>
                <p className="text-xs text-tinta-suave">{COMPARATIVO[i.tipo]}</p>
              </div>

              {i.cargado ? (
                <span className="cifra text-xs text-tinta-suave">
                  {entero(i.filas_cargadas)} filas
                </span>
              ) : null}

              {i.estado === "CON_HALLAZGOS" && (
                <span title="La carga se promovió, pero quedaron descuadres sin resolver">
                  <Chip tono="ambar">con hallazgos</Chip>
                </span>
              )}
              {i.estado === "RECHAZADA" && <Chip tono="rojo">rechazada</Chip>}

              <label className="btn btn-contorno btn-chico shrink-0 cursor-pointer">
                {i.cargado ? "Reemplazar" : "Subir"}
                <input
                  type="file" accept=".xlsx,.xls" className="hidden" disabled={ocupado}
                  onChange={(e) => e.target.files[0] && subir(i.tipo, e.target.files[0])}
                />
              </label>
            </div>
          ))}
        </div>
      </section>

      {ocupado && (
        <p className="mt-6 text-sm text-tinta-media">Procesando el archivo…</p>
      )}

      {/* ------------------------------------------------------- mapeo */}
      {carga?.requiere_mapeo && !resultado && (
        <section className="mt-10 panel p-6">
          <Mapeo
            cargaId={carga.carga_id}
            onListo={() => { setCarga({ ...carga, requiere_mapeo: false }); procesar(carga.carga_id); }}
            onCancelar={() => setCarga(null)}
          />
        </section>
      )}

      {/* --------------------------------------------------- resultado */}
      {resultado && (
        <section className="mt-10 space-y-6">
          <p className="rotulo">Resultado</p>

          {resultado.resultado === "ARCHIVO_IDENTICO" && (
            <Aviso tono="info" titulo="Sin cambios">{resultado.mensaje}</Aviso>
          )}
          {resultado.resultado === "SIN_FILAS_NUEVAS" && (
            <Aviso tono="info" titulo="Sin filas nuevas">{resultado.mensaje}</Aviso>
          )}
          {resultado.resultado === "PRIMERA_CARGA" && (
            <Aviso tono="ok" titulo="Archivo cargado">
              <span className="cifra">{entero(resultado.filas_staging)}</span> filas leídas.
            </Aviso>
          )}
          {resultado.resultado === "CON_CAMBIOS" && (
            <Aviso tono={resultado.n_fuera_periodo > 0 ? "error" : "alerta"}
                   titulo={resultado.n_fuera_periodo > 0
                     ? "Cambios en periodo ya auditado"
                     : "El archivo trae cambios"}>
              {resultado.mensaje}
              <button
                onClick={() => api.evidencia(resultado.cotejo_id).then(setEvidencia)}
                className="ml-2 underline underline-offset-4"
              >
                Ver qué cambió
              </button>
            </Aviso>
          )}

          {resultado.promocion && (
            <>
              <div className="flex gap-8 border-y border-regla py-4">
                <Dato etiqueta="Filas cargadas">
                  <span className="cifra">{entero(resultado.promocion.promovidas)}</span>
                </Dato>
                <Dato etiqueta="Descartadas">
                  <span className="cifra">{entero(resultado.promocion.descartadas)}</span>
                  <span className="ml-2 text-xs text-tinta-suave">
                    niveles fuera de alcance
                  </span>
                </Dato>
                <Dato etiqueta="Descuadres de línea">
                  <span className={`cifra ${resultado.promocion.descuadres_linea ? "text-rojo" : ""}`}>
                    {entero(resultado.promocion.descuadres_linea)}
                  </span>
                </Dato>
              </div>
              <Cuadre cuadre={resultado.promocion.cuadre} />
            </>
          )}

          {evidencia && (
            <div>
              <p className="rotulo mb-3">Evidencia · {evidencia.length} registros</p>
              <div className="overflow-x-auto border border-regla">
                <table className="w-full text-sm">
                  <thead className="bg-papel-hondo">
                    <tr className="rotulo text-left">
                      <th className="px-3 py-2 font-normal">Cambio</th>
                      <th className="px-3 py-2 font-normal">Cuenta</th>
                      <th className="px-3 py-2 font-normal">Documento</th>
                      <th className="px-3 py-2 font-normal">Fecha</th>
                      <th className="px-3 py-2 font-normal">Antes</th>
                      <th className="px-3 py-2 font-normal">Ahora</th>
                      <th className="px-3 py-2 text-center font-normal">Cuadre</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evidencia.map((d, i) => (
                      <tr key={i} className={`border-t border-regla-fina ${
                        d.fuera_periodo ? "bg-rojo-tenue" : ""}`}>
                        <td className="px-3 py-2">
                          <span className="rotulo">{d.cambio}</span>
                        </td>
                        <td className="cifra px-3 py-2">{d.codigo_puc}</td>
                        <td className="cifra px-3 py-2 text-xs">{d.num_doc ?? "—"}</td>
                        <td className="cifra px-3 py-2 text-xs">{fecha(d.fecha)}</td>
                        <td className="cifra px-3 py-2 text-right text-xs text-tinta-suave">
                          {d.valor_antes ? monto(d.valor_antes.saldo_final ?? d.valor_antes.debito) : "—"}
                        </td>
                        <td className="cifra px-3 py-2 text-right text-xs">
                          {d.valor_ahora ? monto(d.valor_ahora.saldo_final ?? d.valor_ahora.debito) : "—"}
                        </td>
                        <td className="px-3 py-2 text-center">
                          {d.descuadre_linea ? (
                            <span title="saldo_inicial + débito - crédito - saldo_final">
                              <span className="rotulo text-rojo">descuadre</span>
                              <span className="cifra ml-1 text-xs text-rojo">
                                {monto(d.descuadre_linea)}
                              </span>
                            </span>
                          ) : d.valor_ahora?.saldo_final !== undefined ? (
                            <Punteo tam={14} />
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}
      </>)}
    </div>
  );
}
