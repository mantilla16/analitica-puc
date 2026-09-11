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
  const [convencion, setConvencion] = useState(null);

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
    api.balance(encargoId, p)
      .then((r) => { setFilas(r.filas); setConvencion(r.convencion_signo); })
      .catch((e) => setError(e.message));
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
                  className={`pestana ${tipo === t ? "pestana-activa" : ""}`}>
            {texto}
          </button>
        ))}
      </div>

      {/* ------------------------------------------------ tarjetas clase */}
      <div>
        <p className="rotulo mb-3">Por clase · saldo comparable (las clases suman cero)</p>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(15rem,1fr))] gap-px bg-regla">
          {resumen.map((c) => (
            <button
              key={c.clase}
              onClick={() => { setBuscar(""); setRuta([c.clase]); }}
              className="bg-papel-alto px-4 py-4 text-left hover:bg-papel-hondo"
            >
              <p className="rotulo">{c.clase} · {c.clase_nombre}</p>
              <p className="cifra mt-2 truncate text-base" title={monto(c.saldo)}>
                {monto(c.saldo)}
              </p>
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
          className="ml-auto w-56 panel px-3 py-1.5 text-sm"
        />
      </div>

      {/* ------------------------------------------------------ tabla */}
      <div className="panel">
        <p className="border-b border-regla bg-papel-hondo px-3 py-2 text-xs text-tinta-suave">
          En pantallas compactas se muestran las cifras clave: saldo final,
          naturaleza y cuadre. Amplie la ventana para ver el movimiento completo.
        </p>
        <div className="overflow-x-auto">
        <table className="w-full min-w-[620px] table-fixed text-sm xl:min-w-[1060px]">
          <colgroup>
            <col className="w-[15%] xl:w-[7%]" />
            <col className="w-[35%] xl:w-[19%]" />
            <col className="hidden xl:table-column xl:w-[14%]" />
            <col className="hidden xl:table-column xl:w-[14%]" />
            <col className="hidden xl:table-column xl:w-[14%]" />
            <col className="w-[25%] xl:w-[14%]" />
            <col className="w-[20%] xl:w-[14%]" />
            <col className="w-[5%] xl:w-[4%]" />
          </colgroup>
          <thead className="border-b border-regla bg-papel-hondo">
            <tr className="rotulo text-left">
              <th className="px-3 py-2 font-normal">Código</th>
              <th className="px-3 py-2 font-normal">Cuenta</th>
              <th className="hidden px-3 py-2 text-right font-normal xl:table-cell">Saldo inicial</th>
              <th className="hidden px-3 py-2 text-right font-normal xl:table-cell">Débito</th>
              <th className="hidden px-3 py-2 text-right font-normal xl:table-cell">Crédito</th>
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
                <td className="whitespace-nowrap px-3 py-2">
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
                <td className="truncate px-3 py-2" title={f.nombre_cuenta ?? "-"}>
                  <button
                    onClick={() => api.detalleCuenta(encargoId, f.codigo_puc).then(setDetalle)}
                    className="text-left hover:underline"
                  >
                    {f.nombre_cuenta ?? "—"}
                  </button>
                </td>
                <td className="hidden cifra px-3 py-2 text-right text-xs xl:table-cell">{monto(f.saldo_inicial)}</td>
                <td className="hidden cifra px-3 py-2 text-right text-xs xl:table-cell">{monto(f.debito)}</td>
                <td className="hidden cifra px-3 py-2 text-right text-xs xl:table-cell">{monto(f.credito)}</td>
                <td className="cifra whitespace-nowrap px-3 py-2 text-right text-xs xl:text-sm">{monto(f.saldo_final)}</td>
                <td className={`cifra whitespace-nowrap px-3 py-2 text-right text-xs xl:text-sm ${
                  Number(f.saldo_naturaleza) < 0 ? "text-rojo" : ""
                }`}>
                  {monto(f.saldo_naturaleza)}
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
      </div>

      <p className="text-xs text-tinta-suave">
        La columna <em>Naturaleza</em> muestra el saldo con el signo de la
        cuenta: positivo si se comporta como debe. En rojo, las que están al
        revés — un banco sobregirado, un proveedor deudor.
        La columna <em>Cuadre</em> marca en rojo la fila donde saldo inicial
        + débito − crédito no da el saldo final reportado.
        {convencion === "ARCHIVO" && (
          <>
            {" "}Este archivo ya trae pasivo, patrimonio e ingresos en
            negativo (convención <span className="cifra">ARCHIVO</span>), así
            que <em>Saldo final</em> y <em>Naturaleza</em> difieren en signo
            para esas clases: la primera es la cifra tal como viene y suma
            cero; la segunda dice de qué lado está el saldo.
          </>
        )}
      </p>

      {detalle && <DetalleCuenta d={detalle} onCerrar={() => setDetalle(null)} />}
    </div>
  );
}

function DetalleCuenta({ d, onCerrar }) {
  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-tinta/25 backdrop-blur-[2px]" onClick={onCerrar}>
      <div
        className="deslizar h-full w-full max-w-2xl overflow-y-auto border-l border-regla bg-papel-alto p-6 shadow-[var(--sombra-alta)]"
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
