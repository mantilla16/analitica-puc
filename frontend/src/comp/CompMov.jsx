import { monto, entero } from "../api";

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

/** "2026-01-01" -> {d, m, a} sin pasar por Date: evita el corrimiento de un
 *  día por zona horaria que sufre `new Date("2026-01-01")`. */
function partes(v) {
  if (!v) return null;
  const [a, m, d] = String(v).slice(0, 10).split("-");
  return { a, m: MESES[Number(m) - 1] ?? m, d: String(Number(d)) };
}

/** "1 ene – 30 jun 2026". Si los años difieren se muestra el año en ambos. */
export function ventanaTexto(v) {
  const i = partes(v?.desde), f = partes(v?.hasta);
  if (!i || !f) return "—";
  return i.a === f.a
    ? `${i.d} ${i.m} – ${f.d} ${f.m} ${f.a}`
    : `${i.d} ${i.m} ${i.a} – ${f.d} ${f.m} ${f.a}`;
}

const num = (v) => (v === null || v === undefined || v === "" ? null : Number(v));

/** Delta con signo y color: el rojo es solo "bajó", no "está mal". */
function Delta({ v }) {
  const n = num(v);
  if (n === null) return <span className="cifra">—</span>;
  return <span className={`cifra ${n < 0 ? "text-rojo" : ""}`}>{monto(n)}</span>;
}

export const pctTexto = (v) => {
  const n = num(v);
  return n === null ? "—" : `${n.toLocaleString("es-CO", { maximumFractionDigits: 1 })} %`;
};

/**
 * Movimientos del periodo contra la misma ventana del año anterior, para UNA
 * cuenta. `datos` = {disponible, motivo, ventana_actual, ventana_anterior,
 * cuenta}. Si `datos` es undefined (backend viejo) no pinta nada: mejor
 * callar que mostrar un "sin datos" que el servidor nunca dijo.
 */
export default function CompMov({ datos }) {
  if (!datos) return null;

  if (!datos.disponible) {
    return (
      <p className="mb-6 text-xs text-tinta-suave">
        {datos.motivo ?? "Sin movimientos del año anterior cargados: no hay comparación."}
      </p>
    );
  }

  const c = datos.cuenta;
  const act = c?.actual, ant = c?.anterior;
  const filas = [
    ["Movimientos", entero(act?.n ?? 0), entero(ant?.n ?? 0)],
    ["Débitos", monto(act?.debito ?? 0), monto(ant?.debito ?? 0)],
    ["Créditos", monto(act?.credito ?? 0), monto(ant?.credito ?? 0)],
    ["Neto", monto(act?.neto ?? 0), monto(ant?.neto ?? 0)],
  ];

  return (
    <section className="mb-8">
      <p className="rotulo mb-1">Movimientos vs mismo periodo del año anterior</p>
      <p className="mb-2 text-xs text-tinta-suave">
        {ventanaTexto(datos.ventana_actual)} contra {ventanaTexto(datos.ventana_anterior)}
      </p>

      {!c ? (
        <p className="text-xs text-tinta-suave">
          La cuenta no tiene movimientos en ninguno de los dos periodos.
        </p>
      ) : (
        <div className="border-t border-regla text-sm">
          <div className="rotulo grid grid-cols-[1fr_1fr_1fr] gap-3 py-1.5">
            <span></span>
            <span className="text-right">Actual</span>
            <span className="text-right">Año anterior</span>
          </div>
          {filas.map(([r, a, b]) => (
            <div key={r}
                 className="grid grid-cols-[1fr_1fr_1fr] gap-3 border-t border-regla-fina py-1.5">
              <span className="text-tinta-suave">{r}</span>
              <span className="cifra text-right">{a}</span>
              <span className="cifra text-right text-tinta-media">{b}</span>
            </div>
          ))}
          <div className="grid grid-cols-[1fr_1fr_1fr] gap-3 border-t border-regla bg-papel-hondo py-1.5">
            <span className="rotulo">Δ</span>
            <span className="text-right">
              <Delta v={c.delta_neto} />
              <span className="ml-1.5 text-xs text-tinta-suave">{pctTexto(c.delta_neto_pct)}</span>
            </span>
            <span className="cifra text-right text-xs text-tinta-suave">
              {num(c.delta_n) === null ? "—" : `${c.delta_n > 0 ? "+" : ""}${entero(c.delta_n)} mov.`}
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
