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
  const [hojas, setHojas] = useState([]);   // puede ser más de una
  const [cols, setCols] = useState({});
  const [error, setError] = useState(null);
  const [avisos, setAvisos] = useState([]);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    api.mapeo(cargaId).then((d) => {
      setDatos(d);
      setHojas(d.hoja_sugerida ? [d.hoja_sugerida] : []);
      const inicial = {};
      d.sugerencia.forEach((s) => { if (s.campo) inicial[s.campo] = s.encabezado; });
      setCols(inicial);
    }).catch((e) => setError(e.message));
  }, [cargaId]);

  if (error) return <Aviso tono="error">{error}</Aviso>;
  if (!datos) return <p className="text-sm text-tinta-suave">Leyendo el archivo…</p>;

  /* Los encabezados que se ofrecen salen de la PRIMERA hoja marcada. Si
     otra no los tiene, el servidor rechaza el mapeo al confirmarlo y dice
     cuál: mejor eso que ofrecer aquí una unión de columnas que en ninguna
     hoja existe entera. */
  const hojaActual = datos.hojas.find((h) => h.hoja === hojas[0]);
  const marcada = (n) => hojas.includes(n);
  const alternarHoja = (n) => setHojas((v) =>
    v.includes(n) ? v.filter((x) => x !== n)
                  : datos.hojas.map((h) => h.hoja).filter(
                      (x) => v.includes(x) || x === n));   // conserva el orden del archivo
  const encabezados = hojaActual?.encabezados ?? [];
  const sinUsar = encabezados.filter((e) => !Object.values(cols).includes(e));
  const faltan = datos.campos_estandar.filter((c) => c.requerido && !cols[c.campo]);

  async function guardar() {
    setGuardando(true);
    setError(null);
    try {
      const r = await api.confirmarMapeo(cargaId, {
        hojas,
        // `hoja` se sigue mandando para que un perfil nuevo lo entiendan
        // también las versiones que solo leen una.
        hoja: hojas[0],
        columnas: cols,
        formato_fecha: "DD/MM/YYYY",
        ignorar_hojas: datos.hojas.map((h) => h.hoja)
                                  .filter((h) => !hojas.includes(h)),
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

      {/* Un archivo que declara mal su propio ancho leia una sola columna:
          el formulario salia sin ninguna opcion que escoger y no habia forma
          de saber por que. Ahora se lee igual y se dice. */}
      {hojaActual?.dimension_mal_declarada && (
        <div className="mb-6">
          <Aviso tono="alerta" titulo="El archivo declara mal su tamaño">
            La hoja <span className="cifra">{hojaActual.hoja}</span> dice usar{" "}
            <span className="cifra">{hojaActual.columnas_declaradas}</span>{" "}
            columna{hojaActual.columnas_declaradas === 1 ? "" : "s"} pero tiene{" "}
            <span className="cifra">{hojaActual.columnas_reales}</span>. Se leyó
            el ancho real; es un defecto del sistema que exportó el archivo, no
            de los datos.
          </Aviso>
        </div>
      )}

      {/* Marcar varias, porque hay ERP que parten un mismo corte en tres
          pestañas. Antes solo se podía elegir una y las demás se perdían sin
          que nada lo dijera: el auditor habría analizado un tercio del
          periodo creyendo que lo tenía completo. */}
      {datos.hojas.length > 1 && (
        <div className="mb-6">
          <p className="rotulo">Hojas por leer</p>
          <p className="mt-1 mb-2 text-xs text-tinta-suave">
            Marque todas las que sean de este mismo insumo. Si el archivo
            reparte el corte en varias, van todas juntas.
          </p>
          <div className="max-w-lg overflow-hidden rounded-[9px] border border-regla">
            {datos.hojas.map((h) => (
              <label key={h.hoja}
                     className={`flex cursor-pointer items-center gap-3 border-b
                                 border-regla-fina px-3 py-2 text-sm last:border-b-0
                                 hover:bg-papel-hondo ${
                                   marcada(h.hoja) ? "bg-papel-hondo" : ""}`}>
                <input type="checkbox" checked={marcada(h.hoja)}
                       onChange={() => alternarHoja(h.hoja)} />
                <span className="min-w-0 flex-1 truncate font-medium">{h.hoja}</span>
                <span className="shrink-0 text-xs text-tinta-suave">
                  {h.fila_encabezado
                    ? `${h.encabezados.length} columnas · ${h.reconocidos} reconocidas`
                    : "sin encabezado reconocible"}
                </span>
              </label>
            ))}
          </div>
          {hojas.length > 1 && (
            <p className="mt-2 text-xs text-tinta-media">
              Se leerán <span className="cifra">{hojas.length}</span> hojas con
              el mismo mapeo. Las columnas de abajo salen de{" "}
              <span className="cifra">{hojas[0]}</span>; si alguna de las otras
              no las tiene, se lo digo al confirmar.
            </p>
          )}
        </div>
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
        <Boton onClick={guardar}
               disabled={guardando || faltan.length > 0 || hojas.length === 0}>
          {guardando ? "Guardando…" : "Confirmar y continuar"}
        </Boton>
        <Boton variante="texto" onClick={onCancelar}>Cancelar</Boton>
        {faltan.length > 0 && (
          <span className="text-xs text-rojo">
            Falta relacionar: {faltan.map((f) => f.etiqueta).join(", ")}
          </span>
        )}
        {hojas.length === 0 && (
          <span className="text-xs text-rojo">Marque al menos una hoja.</span>
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
