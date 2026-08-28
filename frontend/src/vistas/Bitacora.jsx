import { useCallback, useEffect, useState } from "react";
import { api, entero } from "../api";
import { Aviso, Boton, Chip } from "../comp/Piezas";

const PAGINA = 100;
const SIN_FILTRO = { usuario: "", accion: "", desde: "", hasta: "" };

/* Tono por familia de acción: lo que borra o falla debe saltar a la vista
   sin tener que leer el nombre de la acción. */
const TONO = {
  INGRESO_FALLIDO: "rojo",
  ENCARGO_BORRADO: "rojo",
  CLAVE_REINICIADA: "ambar",
  CLAVE_CAMBIADA: "ambar",
  USUARIO_CREADO: "morado",
  USUARIO_EDITADO: "morado",
  INGRESO: "verde",
  SALIDA: "gris",
};

/** Fecha y hora completas: en un rastro de auditoría la hora importa
 *  tanto como el día. */
function cuando(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("es-CO", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function Bitacora({ onVolver }) {
  const [d, setD] = useState(null);
  const [filtro, setFiltro] = useState(SIN_FILTRO);
  const [pagina, setPagina] = useState(0);
  const [error, setError] = useState(null);
  const [abierta, setAbierta] = useState(null);

  const cargar = useCallback(() => {
    api.bitacora({ ...filtro, limite: PAGINA, desplazamiento: pagina * PAGINA })
      .then(setD)
      .catch((e) => setError(e.detalle ?? e.message));
  }, [filtro, pagina]);

  useEffect(() => { cargar(); }, [cargar]);

  const campo = "px-3 py-2 text-sm";
  const hayFiltro = Object.values(filtro).some(Boolean);
  // El total sale del conteo por acción, que ya viene con la respuesta:
  // evita una consulta aparte solo para saber cuántos registros hay.
  const total = (d?.acciones ?? []).reduce((n, a) => n + Number(a.n), 0);
  const editar = (k) => (e) => {
    setPagina(0);
    setFiltro({ ...filtro, [k]: e.target.value });
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <button onClick={onVolver} className="rotulo mb-8 hover:text-tinta">
        ← Encargos
      </button>

      <header className="mb-8 border-b border-regla pb-6">
        <p className="rotulo">Administración</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Bitácora</h1>
        <p className="mt-2 max-w-2xl text-sm text-tinta-media">
          Quién hizo qué, cuándo y desde dónde. Se registran los ingresos y
          todo lo que modifica datos; las consultas de lectura no, porque
          serían ruido y no cambian nada.
        </p>
      </header>

      {error && <div className="mb-6"><Aviso tono="error">{String(error)}</Aviso></div>}

      {/* ------------------------------------------------------ filtros */}
      {/* Agrupados en un panel: sueltos sobre el fondo parecían campos
          abandonados, y no se leía que actúan sobre la tabla de abajo. */}
      <div className="panel mb-5 flex flex-wrap items-end gap-4 p-4">
        <label className="block">
          <span className="rotulo">Usuario</span>
          <input value={filtro.usuario} onChange={editar("usuario")}
                 placeholder="todos" className={`${campo} mt-1.5 w-40`} />
        </label>
        <label className="block">
          <span className="rotulo">Acción</span>
          <select value={filtro.accion} onChange={editar("accion")}
                  className={`${campo} mt-1.5 w-60`}>
            <option value="">Todas</option>
            {(d?.acciones ?? []).map((a) => (
              <option key={a.accion} value={a.accion}>
                {a.accion} ({a.n})
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="rotulo">Desde</span>
          <input type="date" value={filtro.desde} onChange={editar("desde")}
                 className={`cifra ${campo} mt-1.5`} />
        </label>
        <label className="block">
          <span className="rotulo">Hasta</span>
          <input type="date" value={filtro.hasta} onChange={editar("hasta")}
                 className={`cifra ${campo} mt-1.5`} />
        </label>
        {hayFiltro && (
          <Boton variante="texto"
                 onClick={() => { setPagina(0); setFiltro(SIN_FILTRO); }}>
            Limpiar
          </Boton>
        )}
        <span className="ml-auto self-center text-xs text-tinta-suave">
          {entero(d?.filas.length ?? 0)} de {entero(total)} registros
        </span>
      </div>

      {/* ------------------------------------------------------- tabla */}
      <div className="overflow-x-auto panel tabla">
        <table className="w-full text-sm">
          <thead>
            <tr className="rotulo border-b border-regla text-left">
              <th className="px-3 py-2 font-normal">Fecha y hora</th>
              <th className="px-3 py-2 font-normal">Usuario</th>
              <th className="px-3 py-2 font-normal">Acción</th>
              <th className="px-3 py-2 font-normal">Cliente</th>
              <th className="px-3 py-2 font-normal">Origen</th>
              <th className="px-3 py-2 font-normal">Detalle</th>
            </tr>
          </thead>
          <tbody>
            {d && d.filas.length === 0 && (
              <tr><td colSpan={6} className="px-3 py-10 text-center text-tinta-suave">
                Sin registros para ese filtro.
              </td></tr>
            )}
            {(d?.filas ?? []).map((b) => (
              <tr key={b.id} className="border-b border-regla-fina">
                <td className="cifra whitespace-nowrap px-3 py-2 text-xs">
                  {cuando(b.creado_en)}
                </td>
                <td className="px-3 py-2 text-sm">{b.usuario ?? "—"}</td>
                <td className="px-3 py-2">
                  <Chip tono={b.exito ? (TONO[b.accion] ?? "cian") : "rojo"}>
                    {b.accion}
                  </Chip>
                </td>
                <td className="max-w-[14rem] truncate px-3 py-2 text-xs"
                    title={b.razon_social ?? ""}>
                  {b.razon_social ?? "—"}
                </td>
                <td className="cifra px-3 py-2 text-xs text-tinta-suave">
                  {b.ip ?? "—"}
                </td>
                <td className="px-3 py-2 text-xs">
                  {b.detalle ? (
                    <button onClick={() => setAbierta(abierta === b.id ? null : b.id)}
                            className="rotulo text-tinta-suave hover:text-tinta">
                      {abierta === b.id ? "Ocultar" : "Ver"}
                    </button>
                  ) : "—"}
                  {abierta === b.id && (
                    <pre className="cifra mt-2 max-w-md overflow-x-auto rounded-[8px]
                                    bg-papel-hondo p-3 text-[11px] leading-relaxed">
                      {JSON.stringify(b.detalle, null, 2)}
                    </pre>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ---------------------------------------------------- paginado */}
      <div className="mt-4 flex items-center gap-4">
        <Boton variante="contorno" disabled={pagina === 0}
               onClick={() => setPagina(pagina - 1)}>
          ← Anteriores
        </Boton>
        <span className="text-xs text-tinta-suave">
          {entero(pagina * PAGINA + 1)}–{entero(pagina * PAGINA + (d?.filas.length ?? 0))}
        </span>
        <Boton variante="contorno"
               disabled={(d?.filas.length ?? 0) < PAGINA}
               onClick={() => setPagina(pagina + 1)}>
          Siguientes →
        </Boton>
      </div>

      <p className="mt-6 max-w-2xl text-xs leading-relaxed text-tinta-suave">
        Los ingresos fallidos se registran con el motivo real —usuario
        inexistente, cuenta desactivada o contraseña incorrecta—, aunque a
        quien intenta entrar siempre se le responda lo mismo. Varios
        seguidos desde una misma dirección merecen una mirada.
      </p>
    </div>
  );
}
