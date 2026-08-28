import { useEffect, useState } from "react";
import { api } from "../api";
import { Aviso, Boton } from "../comp/Piezas";

/**
 * El auditor relaciona SUS columnas contra el estándar del sistema.
 * Lo que reconoce automáticamente viene preseleccionado; solo completa
 * lo que falte. Se guarda una vez por cliente y no vuelve a preguntar.
 */
export default function Mapeo({ cargaId, onListo, onCancelar }) {
  const [datos, setDatos] = useState(null);
  const [hoja, setHoja] = useState("");
  const [cols, setCols] = useState({});
  const [error, setError] = useState(null);
  const [avisos, setAvisos] = useState([]);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    api.mapeo(cargaId).then((d) => {
      setDatos(d);
      setHoja(d.hoja_sugerida ?? "");
      const inicial = {};
      d.sugerencia.forEach((s) => { if (s.campo) inicial[s.campo] = s.encabezado; });
      setCols(inicial);
    }).catch((e) => setError(e.message));
  }, [cargaId]);

  if (error) return <Aviso tono="error">{error}</Aviso>;
  if (!datos) return <p className="text-sm text-tinta-suave">Leyendo el archivo…</p>;

  const hojaActual = datos.hojas.find((h) => h.hoja === hoja);
  const encabezados = hojaActual?.encabezados ?? [];
  const sinUsar = encabezados.filter((e) => !Object.values(cols).includes(e));
  const faltan = datos.campos_estandar.filter((c) => c.requerido && !cols[c.campo]);

  async function guardar() {
    setGuardando(true);
    setError(null);
    try {
      const r = await api.confirmarMapeo(cargaId, {
        hoja,
        columnas: cols,
        formato_fecha: "DD/MM/YYYY",
        ignorar_hojas: datos.hojas.map((h) => h.hoja).filter((h) => h !== hoja),
      });
      setAvisos(r.avisos ?? []);
      onListo();
    } catch (e) {
      setError(
        Array.isArray(e.detalle)
          ? e.detalle.map((p) => `${p.problema}: ${p.detalle}`).join(" · ")
          : e.message
      );
      setGuardando(false);
    }
  }

  return (
    <div>
      <div className="mb-6">
        <p className="rotulo">Relacionar columnas</p>
        <p className="mt-1 text-sm text-tinta-media">
          Es la primera vez que se carga este tipo de archivo para{" "}
          {datos.cliente}. Indique qué columna del Excel corresponde a cada campo.
          Queda guardado para las próximas cargas.
        </p>
      </div>

      {datos.hojas.length > 1 && (
        <label className="mb-6 block max-w-xs">
          <span className="rotulo">Hoja</span>
          <select
            value={hoja}
            onChange={(e) => setHoja(e.target.value)}
            className="mt-1 w-full px-3 py-2 text-sm"
          >
            {datos.hojas.map((h) => (
              <option key={h.hoja} value={h.hoja}>
                {h.hoja} — {h.encabezados.length} columnas, {h.reconocidos} reconocidas
              </option>
            ))}
          </select>
        </label>
      )}

      {error && <div className="mb-4"><Aviso tono="error">{error}</Aviso></div>}

      <div className="border-t border-regla">
        {datos.campos_estandar.map((c) => {
          const valor = cols[c.campo] ?? "";
          const auto = datos.sugerencia.some(
            (s) => s.campo === c.campo && s.encabezado === valor
          );
          return (
            <div key={c.campo}
                 className="grid grid-cols-[1fr_1.2fr] items-center gap-6 border-b border-regla-fina py-3">
              <div>
                <span className="text-sm font-medium">{c.etiqueta}</span>
                {c.requerido && <span className="ml-1.5 text-rojo">*</span>}
                {c.ayuda && (
                  <p className="mt-0.5 text-xs leading-snug text-tinta-suave">{c.ayuda}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={valor}
                  onChange={(e) =>
                    setCols({ ...cols, [c.campo]: e.target.value || undefined })
                  }
                  className={`w-full border px-3 py-1.5 text-sm bg-papel-alto ${
                    !valor && c.requerido ? "border-rojo" : "border-regla"
                  }`}
                >
                  <option value="">— sin relacionar —</option>
                  {encabezados.map((e) => (
                    <option key={e} value={e}>{e}</option>
                  ))}
                </select>
                {auto && valor && (
                  <span className="rotulo shrink-0 text-verde">auto</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {sinUsar.length > 0 && (
        <p className="mt-4 text-xs text-tinta-suave">
          Sin usar: {sinUsar.join(" · ")}
        </p>
      )}

      <div className="mt-8 flex items-center gap-3">
        <Boton onClick={guardar} disabled={guardando || faltan.length > 0}>
          {guardando ? "Guardando…" : "Confirmar y continuar"}
        </Boton>
        <Boton variante="texto" onClick={onCancelar}>Cancelar</Boton>
        {faltan.length > 0 && (
          <span className="text-xs text-rojo">
            Falta relacionar: {faltan.map((f) => f.etiqueta).join(", ")}
          </span>
        )}
      </div>

      {avisos.length > 0 && (
        <div className="mt-4 space-y-2">
          {avisos.map((a, i) => (
            <Aviso key={i} tono="alerta" titulo={a.problema}>{a.detalle}</Aviso>
          ))}
        </div>
      )}
    </div>
  );
}
