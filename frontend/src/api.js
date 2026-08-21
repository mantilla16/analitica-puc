const BASE = import.meta.env.VITE_API ?? "/api";

async function pedir(ruta, opciones = {}) {
  const r = await fetch(BASE + ruta, opciones);
  const texto = await r.text();
  let cuerpo = null;
  try { cuerpo = texto ? JSON.parse(texto) : null; } catch { cuerpo = texto; }
  if (!r.ok) {
    const e = new Error(cuerpo?.detail ? JSON.stringify(cuerpo.detail) : r.statusText);
    e.estado = r.status;
    e.detalle = cuerpo?.detail ?? cuerpo;
    throw e;
  }
  return cuerpo;
}

const json = (metodo, cuerpo) => ({
  method: metodo,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(cuerpo),
});

export const api = {
  encargos: () => pedir("/encargos"),
  encargo: (id) => pedir(`/encargos/${id}`),
  crearEncargo: (d) => pedir("/encargos", json("POST", d)),
  eliminarEncargo: (id) => pedir(`/encargos/${id}`, { method: "DELETE" }),
  checklist: (id) => pedir(`/encargos/${id}/checklist`),

  subir: (encargoId, form) =>
    pedir(`/encargos/${encargoId}/cargas`, { method: "POST", body: form }),

  mapeo: (cargaId) => pedir(`/cargas/${cargaId}/mapeo`),
  confirmarMapeo: (cargaId, d) => pedir(`/cargas/${cargaId}/mapeo`, json("POST", d)),
  procesar: (cargaId) =>
    pedir(`/cargas/${cargaId}/procesar?sincrono=true`, { method: "POST" }),
  promover: (cargaId) => pedir(`/cargas/${cargaId}/promover`, { method: "POST" }),
  carga: (cargaId) => pedir(`/cargas/${cargaId}`),
  evidencia: (cotejoId) => pedir(`/cotejos/${cotejoId}/evidencia?limite=100`),

  fases: () => pedir("/fases"),
  materialidades: (id) => pedir(`/encargos/${id}/materialidades`),
  guardarMaterialidad: (id, fase, d) =>
    pedir(`/encargos/${id}/materialidades/${fase}`, json("PUT", d)),
  fijarFase: (id, fase) => pedir(`/encargos/${id}/fase/${fase}`, { method: "PUT" }),
  guardarParametros: (id, d) => pedir(`/encargos/${id}/parametros`, json("PUT", d)),

  resumen: (id, tipo) => pedir(`/encargos/${id}/resumen${tipo ? `?tipo=${tipo}` : ""}`),
  balance: (id, params) => pedir(`/encargos/${id}/balance?${params}`),
  variaciones: (id, fase) =>
    pedir(`/encargos/${id}/variaciones${fase ? `?fase=${fase}` : ""}`),
  observaciones: (id, fase) => pedir(`/encargos/${id}/variaciones/${fase}/observaciones`),
  observacionCuenta: (id, fase, codigo) =>
    pedir(`/encargos/${id}/variaciones/${fase}/observacion/${codigo}`),
  detalleCuenta: (id, codigo) => pedir(`/encargos/${id}/cuentas/${codigo}`),
};

// ------------------------------------------------------------------ formato

const pesos = new Intl.NumberFormat("es-CO", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export const monto = (v) =>
  v === null || v === undefined || v === "" ? "—" : pesos.format(Number(v));

export const entero = (v) =>
  v === null || v === undefined ? "—" : new Intl.NumberFormat("es-CO").format(v);

export const fecha = (v) => {
  if (!v) return "—";
  const [a, m, d] = String(v).slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
};

/** Periodos que corresponden a cada insumo, derivados del encargo.
 *  Evita que el auditor teclee fechas que el sistema ya conoce. */
export function periodoDe(tipo, encargo) {
  if (!encargo) return { ini: "", fin: "" };
  const corte = encargo.fecha_corte;
  const anio = Number(corte.slice(0, 4));
  const cierreAnt = encargo.fecha_cierre_anterior;
  const corteAnt = encargo.fecha_corte_anterior;

  switch (tipo) {
    case "BAL_ACTUAL":
    case "MOV_ACTUAL":
      return { ini: `${anio}-01-01`, fin: corte };
    case "BAL_CIERRE_ANTERIOR":
    case "MOV_ANTERIOR":
      return { ini: `${anio - 1}-01-01`, fin: cierreAnt };
    case "BAL_CORTE_ANTERIOR":
      return { ini: `${anio - 1}-01-01`, fin: corteAnt };
    default:
      return { ini: `${anio}-01-01`, fin: corte };
  }
}

export const COMPARATIVO = {
  BAL_ACTUAL: "Base del análisis",
  BAL_CIERRE_ANTERIOR: "Comparativo de clases 1 · 2 · 3",
  BAL_CORTE_ANTERIOR: "Comparativo de clases 4 · 5 · 6 · 7",
  MOV_ACTUAL: "Detalle del periodo",
  MOV_ANTERIOR: "Detalle del año anterior",
  PRECOMPROBANTE: "Opcional",
};
