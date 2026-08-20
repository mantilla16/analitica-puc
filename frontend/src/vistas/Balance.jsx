import { useEffect, useState } from "react";
import { api, monto, entero } from "../api";
import { Aviso, Punteo } from "../comp/Piezas";

const NIVELES = ["Clase", "Cuenta", "Subcuenta", "Auxiliar"];

const PERIODOS = [
  ["BAL_ACTUAL", "Corte actual"],
  ["BAL_CIERRE_ANTERIOR", "Cierre anterior"],
  ["BAL_CORTE_ANTERIOR", "Corte anterior (año pasado)"],
];

/**
 * Navegación por la jerarquía del balance.
 *
 * Cada nivel completo es el mismo balance más desglosado, así que se
 * entra por clase y se baja: 1 -> 1105 -> 110505 -> 11050501.
 *
 * Solo se navega un balance a la vez: el actual y los dos comparativos
 * son cargas distintas, cada una con su propia jerarquía.
 */
export default function Balance({ encargoId }) {
  const [tipo, setTipo] = useState("BAL_ACTUAL");
  const [resumen, setResumen] = useState([]);
  const [ruta, setRuta] = useState([]);           // migas: códigos padre
  const [filas, setFilas] = useState([]);
  const [buscar, setBuscar] = useState("");
  const [detalle, setDetalle] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.resumen(encargoId, tipo).then(setResumen).catch((e) => setError(e.message));
  }, [encargoId, tipo]);

  useEffect(() => {
    const padre = ruta.at(-1);
    const p = new URLSearchParams();
    p.set("tipo", tipo);
    if (padre) p.set("padre", padre);
    else if (!buscar) p.set("nivel", "Clase");
    if (buscar) p.set("buscar", buscar);
    api.balance(encargoId, p).then((r) => setFilas(r.filas)).catch((e) => setError(e.message));
  }, [encargoId, tipo, ruta, buscar]);

  function cambiarTipo(t) {
    setTipo(t);
    setRuta([]);
    setBuscar("");
  }

  const totalActivo = resumen.find((r) => r.clase === "1");

  return (
    <div className="space-y-8">
      {error && <Aviso tono="error">{error}</Aviso>}

      {/* ----------------------------------------------------- periodo */}
      <div className="flex flex-wrap items-center gap-1 border-b border-regla pb-3">
        <span className="rotulo mr-2">Balance</span>
        {PERIODOS.map(([t, texto]) => (
          <button key={t} onClick={() => cambiarTipo(t)}
                  className={`px-3 py-1 text-sm ${
                    tipo === t
                      ? "bg-tinta text-papel"
                      : "text-tinta-suave hover:text-tinta"}`}>
            {texto}
          </button>
        ))}
      </div>

      {/* ------------------------------------------------ tarjetas clase */}
      <div>
        <p className="rotulo mb-3">Por clase · saldo en naturaleza</p>
        <div className="grid grid-cols-2 gap-px bg-regla sm:grid-cols-3 lg:grid-cols-6">
          {resumen.map((c) => (
            <button
              key={c.clase}
              onClick={() => { setBuscar(""); setRuta([c.clase]); }}
              className="bg-papel-alto px-4 py-4 text-left hover:bg-papel-hondo"
            >
              <p className="rotulo">{c.clase} · {c.clase_nombre}</p>
              <p className="cifra mt-2 text-base">{monto(c.saldo)}</p>
              <p className="mt-1 text-xs text-tinta-suave">
                {entero(c.cuentas)} cuentas
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* ------------------------------------------------------- migas */}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <button
          onClick={() => { setRuta([]); setBuscar(""); }}
          className="rotulo hover:text-tinta"
        >
          Todas las clases
        </button>
        {ruta.map((r, i) => (
          <span key={r} className="flex items-center gap-2">
            <span className="text-tinta-suave">/</span>
            <button
              onClick={() => setRuta(ruta.slice(0, i + 1))}
              className="cifra hover:underline"
            >
              {r}
            </button>
          </span>
        ))}

        <input
          value={buscar}
          onChange={(e) => { setBuscar(e.target.value); setRuta([]); }}
          placeholder="Buscar código o nombre"
          className="ml-auto w-56 border border-regla bg-papel-alto px-3 py-1.5 text-sm"
        />
      </div>

      {/* ------------------------------------------------------ tabla */}
      <div className="overflow-x-auto border border-regla bg-papel-alto">
        <table className="w-full text-sm">
          <thead className="border-b border-regla bg-papel-hondo">
            <tr className="rotulo text-left">
              <th className="px-3 py-2 font-normal">Código</th>
              <th className="px-3 py-2 font-normal">Cuenta</th>
              <th className="px-3 py-2 text-right font-normal">Saldo inicial</th>
              <th className="px-3 py-2 text-right font-normal">Débito</th>
              <th className="px-3 py-2 text-right font-normal">Crédito</th>
              <th className="px-3 py-2 text-right font-normal">Saldo final</th>
              <th className="px-3 py-2 text-right font-normal">Naturaleza</th>
              <th className="px-3 py-2 text-center font-normal">Cuadre</th>
            </tr>
          </thead>
          <tbody>
            {filas.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-10 text-center text-tinta-suave">
                  {buscar ? "Ningún código coincide." : "Sin filas en este nivel."}
                </td>
              </tr>
            )}
            {filas.map((f) => (
              <tr key={f.codigo_puc} className="border-b border-regla-fina hover:bg-papel-hondo">
                <td className="px-3 py-2">
                  {f.tiene_hijos ? (
                    <button
                      onClick={() => { setBuscar(""); setRuta([...ruta, f.codigo_puc]); }}
                      className="cifra underline underline-offset-4 hover:text-verde"
                    >
                      {f.codigo_puc}
                    </button>
                  ) : (
                    <span className="cifra">{f.codigo_puc}</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  <button
                    onClick={() => api.detalleCuenta(encargoId, f.codigo_puc).then(setDetalle)}
                    className="text-left hover:underline"
                  >
                    {f.nombre_cuenta ?? "—"}
                  </button>
                </td>
                <td className="cifra px-3 py-2 text-right text-xs">{monto(f.saldo_inicial)}</td>
                <td className="cifra px-3 py-2 text-right text-xs">{monto(f.debito)}</td>
                <td className="cifra px-3 py-2 text-right text-xs">{monto(f.credito)}</td>
                <td className="cifra px-3 py-2 text-right">{monto(f.saldo_final)}</td>
                <td className={`cifra px-3 py-2 text-right ${
                  Number(f.saldo_natural) < 0 ? "text-rojo" : ""
                }`}>
                  {monto(f.saldo_natural)}
                </td>
                <td className="px-3 py-2 text-center">
                  {f.descuadre_linea ? (
                    <span title="saldo_inicial + débito - crédito - saldo_final">
                      <span className="rotulo text-rojo">descuadre</span>
                      <span className="cifra ml-1 text-xs text-rojo">
                        {monto(f.descuadre_linea)}
                      </span>
                    </span>
                  ) : (
                    <Punteo tam={14} />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-tinta-suave">
        La columna <em>Naturaleza</em> muestra el saldo con el signo de la
        cuenta: positivo si se comporta como debe. En rojo, las que están al
        revés — un banco sobregirado, un proveedor deudor.
        La columna <em>Cuadre</em> marca en rojo la fila donde saldo inicial
        + débito − crédito no da el saldo final reportado.
      </p>

      {detalle && <DetalleCuenta d={detalle} onCerrar={() => setDetalle(null)} />}
    </div>
  );
}

function DetalleCuenta({ d, onCerrar }) {
  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-tinta/20" onClick={onCerrar}>
      <div
        className="h-full w-full max-w-2xl overflow-y-auto border-l border-regla bg-papel p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-6 flex items-start justify-between">
          <div>
            <p className="rotulo">Cuenta</p>
            <p className="cifra mt-1 text-2xl">{d.codigo}</p>
          </div>
          <button onClick={onCerrar} className="rotulo hover:text-tinta">Cerrar ✕</button>
        </div>

        {d.hijos.length > 0 && (
          <section className="mb-8">
            <p className="rotulo mb-2">Composición · {d.hijos.length} subcuentas</p>
            <div className="border-t border-regla">
              {d.hijos.slice(0, 40).map((h) => (
                <div key={h.codigo_puc}
                     className="flex items-baseline gap-3 border-b border-regla-fina py-2 text-sm">
                  <span className="cifra w-24 shrink-0 text-xs">{h.codigo_puc}</span>
                  <span className="flex-1 truncate">{h.nombre_cuenta}</span>
                  <span className="cifra">{monto(h.saldo_final)}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {d.patrones.length > 0 && (
          <section className="mb-8">
            <p className="rotulo mb-2">Qué se movió · agrupado por descripción</p>
            <div className="border-t border-regla">
              {d.patrones.map((p, i) => (
                <div key={i} className="flex items-baseline gap-3 border-b border-regla-fina py-2 text-sm">
                  <span className="cifra w-10 shrink-0 text-xs text-tinta-suave">
                    {p.veces}×
                  </span>
                  <span className="flex-1 truncate">{p.descripcion ?? "—"}</span>
                  <span className="cifra">{monto(p.neto)}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {d.movimientos.length > 0 ? (
          <section>
            <p className="rotulo mb-2">Movimientos más grandes</p>
            <div className="border-t border-regla">
              {d.movimientos.slice(0, 30).map((m, i) => (
                <div key={i} className="border-b border-regla-fina py-2 text-sm">
                  <div className="flex items-baseline gap-3">
                    <span className="cifra w-20 shrink-0 text-xs">{m.fecha}</span>
                    <span className="cifra flex-1 truncate text-xs">{m.num_doc}</span>
                    <span className="cifra">
                      {monto(Number(m.debito) - Number(m.credito))}
                    </span>
                  </div>
                  <p className="mt-0.5 truncate text-xs text-tinta-suave">
                    {m.tercero_nombre} · {m.descripcion}
                  </p>
                </div>
              ))}
            </div>
          </section>
        ) : (
          <p className="text-sm text-tinta-suave">
            Cargue los movimientos del periodo para ver el detalle de esta cuenta.
          </p>
        )}
      </div>
    </div>
  );
}
