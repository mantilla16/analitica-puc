import { useEffect, useState } from "react";
import { api, fecha } from "../api";
import { Aviso, Boton, Chip, Confirmar, Modal } from "../comp/Piezas";

export default function Encargos({ yo, onAbrir }) {
  const [lista, setLista] = useState([]);
  const [creando, setCreando] = useState(false);
  const [error, setError] = useState(null);
  const [borrando, setBorrando] = useState(null);   // encargo por confirmar
  const [usuarios, setUsuarios] = useState([]);
  const [editando, setEditando] = useState(null);   // encargo en edición
  const [ed, setEd] = useState(null);               // sus campos
  const [choque, setChoque] = useState(null);       // insumos desalineados
  const [form, setForm] = useState({
    nit: "", razon_social: "", fecha_corte: "",
  });

  useEffect(() => { refrescar(); }, []);

  useEffect(() => {
    if (yo?.rol !== "ADMIN") return;
    api.usuarios().then((r) => setUsuarios(r.filter((u) => u.activo))).catch((e) => setError(e.message));
  }, [yo?.rol]);

  function refrescar() {
    api.encargos().then(setLista).catch((e) => setError(e.message));
  }

  async function eliminar(enc) {
    setBorrando(null);
    try {
      await api.eliminarEncargo(enc.id);
      refrescar();
    } catch (err) {
      setError(err.message);
    }
  }

  async function crear(e) {
    e.preventDefault();
    setError(null);
    try {
      const enc = await api.crearEncargo(form);
      onAbrir(enc.id);
    } catch (err) {
      setError(err.message);
    }
  }

  function abrirEdicion(enc) {
    setEditando(enc);
    setChoque(null);
    setEd({
      razon_social: enc.razon_social ?? "",
      responsable: enc.creado_por ?? "",
      estado: enc.estado ?? "ABIERTO",
      fecha_corte: enc.fecha_corte ?? "",
      fecha_cierre_anterior: enc.fecha_cierre_anterior ?? "",
      fecha_corte_anterior: enc.fecha_corte_anterior ?? "",
    });
  }

  /* Al mover el corte se recalculan las dos fechas comparativas, que es lo
     que el sistema haría al crear el encargo. Quedan editables: hay cierres
     que no caen el 31 de diciembre. */
  function cambiarCorte(valor) {
    const d = new Date(`${valor}T00:00:00`);
    if (isNaN(d)) return setEd({ ...ed, fecha_corte: valor });
    const a = d.getFullYear() - 1;
    const mes = String(d.getMonth() + 1).padStart(2, "0");
    const dia = String(d.getDate()).padStart(2, "0");
    setEd({
      ...ed,
      fecha_corte: valor,
      fecha_cierre_anterior: `${a}-12-31`,
      fecha_corte_anterior: `${a}-${mes}-${dia}`,
    });
  }

  async function guardarEdicion(confirmar = false) {
    if (!editando) return;
    setError(null);
    try {
      // El responsable va por su propia ruta: cambia quién tiene acceso, no
      // solo un dato de la ficha, y queda en la bitácora como tal.
      if (ed.responsable && ed.responsable !== editando.creado_por) {
        await api.reasignarEncargo(editando.id, ed.responsable);
      }
      await api.editarEncargo(editando.id, {
        razon_social: ed.razon_social,
        estado: ed.estado,
        fecha_corte: ed.fecha_corte,
        fecha_cierre_anterior: ed.fecha_cierre_anterior,
        fecha_corte_anterior: ed.fecha_corte_anterior,
        confirmar,
      });
      setEditando(null);
      setChoque(null);
      refrescar();
    } catch (err) {
      if (err.estado === 409 && err.detalle?.desalineados) {
        setChoque(err.detalle);      // no se guarda: primero que lo vea
      } else {
        setError(err.detalle?.problema ?? err.message);
      }
    }
  }

  const campo = (k) => ({
    value: form[k],
    onChange: (e) => setForm({ ...form, [k]: e.target.value }),
    className:
      "w-full px-3 py-2 text-sm",
  });

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <header className="mb-12 border-b border-regla pb-6">
        <p className="rotulo">Russell Bedford · Analítica</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">
          Balances y movimientos
        </h1>
        <p className="mt-2 max-w-xl text-sm text-tinta-media">
          Cargue los balances y movimientos del cliente. El sistema los valida,
          detecta recargas y deja la evidencia de lo que cambió.
        </p>
      </header>

      {error && <div className="mb-6"><Aviso tono="error">{error}</Aviso></div>}

      {!creando ? (
        <>
          <div className="mb-4 flex items-center justify-between">
            <p className="rotulo">Encargos abiertos</p>
            <Boton onClick={() => setCreando(true)}>Nuevo encargo</Boton>
          </div>

          {lista.length === 0 ? (
            <div className="rounded-[12px] border border-dashed border-regla
                            bg-papel-alto/60 px-6 py-16 text-center">
              <p className="text-sm text-tinta-media">
                Todavía no hay encargos. Cree el primero para empezar a cargar archivos.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {lista.map((e) => (
                <div key={e.id}
                     className="panel tarjeta-activa flex w-full items-center gap-5 px-5 py-4">
                  <button
                    onClick={() => onAbrir(e.id)}
                    className="flex flex-1 items-center gap-5 text-left"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block font-semibold">{e.razon_social}</span>
                      <span className="cifra block text-xs text-tinta-suave">{e.nit}</span>
                    </span>
                    <span className="cifra text-sm">{fecha(e.fecha_corte)}</span>
                    {yo?.rol === "ADMIN" && (
                      <span className="hidden text-xs text-tinta-suave sm:inline">
                        {e.creado_por_nombre ?? "Sin asignar"}
                      </span>
                    )}
                    <Chip tono={e.estado === "ABIERTO" ? "verde" : "gris"}>
                      {e.estado}
                    </Chip>
                  </button>
                  {yo?.rol === "ADMIN" && (
                    <button
                      onClick={(ev) => { ev.stopPropagation(); abrirEdicion(e); }}
                      className="rotulo shrink-0 text-tinta-suave hover:text-marca"
                      title="Editar la ficha del encargo"
                    >
                      Editar
                    </button>
                  )}
                  <button
                    onClick={(ev) => { ev.stopPropagation(); setBorrando(e); }}
                    className="rotulo shrink-0 text-tinta-suave hover:text-rojo"
                    title="Borrar este encargo"
                  >
                    Borrar
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <form onSubmit={crear} className="max-w-lg">
          <p className="rotulo mb-6">Nuevo encargo</p>

          <div className="space-y-5">
            <label className="block">
              <span className="rotulo">NIT</span>
              <input {...campo("nit")} required placeholder="901228343-1" className={`${campo("nit").className} cifra mt-1`} />
            </label>

            <label className="block">
              <span className="rotulo">Razón social</span>
              <input {...campo("razon_social")} required placeholder="LIQUITECH S.A.S." className={`${campo("razon_social").className} mt-1`} />
            </label>

            <label className="block">
              <span className="rotulo">Fecha de corte</span>
              <input type="date" {...campo("fecha_corte")} required className={`${campo("fecha_corte").className} cifra mt-1`} />
              <span className="mt-1 block text-xs text-tinta-suave">
                Los dos periodos comparativos se calculan a partir de esta fecha.
                Las materialidades se registran después, en su pestaña.
              </span>
            </label>

            {/* El responsable ya no se escoge: es quien esta en sesion, y lo
                pone el servidor. Un selector aqui daria a entender que se
                puede abrir un encargo a nombre de otro, y el servidor
                ignoraria el valor. */}
            <div>
              <span className="rotulo">Responsable</span>
              <p className="mt-1 py-2 text-sm font-medium">
                {yo?.nombre ?? "—"}
                <span className="ml-1.5 text-xs text-tinta-suave">(usted)</span>
              </p>
              <span className="mt-1 block text-xs leading-snug text-tinta-suave">
                Queda a su nombre y solo usted lo ve. Los papeles que salgan
                de este encargo se firman con estos datos.
              </span>
            </div>
          </div>

          <div className="mt-8 flex gap-3">
            <Boton type="submit">Abrir encargo</Boton>
            <Boton type="button" variante="texto" onClick={() => setCreando(false)}>
              Cancelar
            </Boton>
          </div>
        </form>
      )}

      {borrando && (
        <Confirmar
          rotulo="Acción irreversible"
          titulo={`Borrar el encargo de ${borrando.razon_social}`}
          textoAccion="Borrar encargo"
          onConfirmar={() => eliminar(borrando)}
          onCerrar={() => setBorrando(null)}
        >
          <p>
            Corte del <span className="cifra">{fecha(borrando.fecha_corte)}</span>.
          </p>
          <p className="mt-3">
            Se pierden las materialidades digitadas, los parámetros de
            selección y los análisis de IA de este encargo.
          </p>
          <p className="mt-3">
            Los archivos que ya subió el cliente <strong>no</strong> se pierden,
            pero habrá que volver a asignarlos en un encargo nuevo.
          </p>
        </Confirmar>
      )}

      {editando && ed && (
        <Modal titulo="Editar encargo" rotulo={editando.nit}
               ancho="max-w-lg" onCerrar={() => { setEditando(null); setChoque(null); }}>

          {/* La advertencia va ANTES del formulario y no se puede pasar por
              alto: es la única pantalla donde un cambio puede dejar el papel
              comparando periodos que no corresponden. */}
          {choque && (
            <div className="mb-5">
              <Aviso tono="error" titulo="Hay archivos que dejarían de corresponder">
                <p>
                  Estas fechas no coinciden con el periodo de los archivos ya
                  cargados:
                </p>
                <ul className="mt-2 space-y-1">
                  {choque.desalineados.map((d) => (
                    <li key={d.tipo} className="text-xs">
                      <span className="cifra">{d.tipo}</span> cierra al{" "}
                      <span className="cifra">{d.tenia}</span> y debería cerrar
                      al <span className="cifra">{d.deberia}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-2">
                  Si continúa, esos insumos quedan marcados como bloqueantes y
                  hay que volver a subirlos. El papel no se arma mientras tanto.
                </p>
              </Aviso>
            </div>
          )}

          <div className="space-y-4">
            <label className="block">
              <span className="rotulo">Razón social</span>
              <input value={ed.razon_social}
                     onChange={(e) => setEd({ ...ed, razon_social: e.target.value })}
                     className="mt-1.5 w-full px-3 py-2 text-sm" />
              <span className="mt-1 block text-xs text-tinta-suave">
                Es del cliente: cambia en todos sus encargos.
              </span>
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="rotulo">Responsable</span>
                <select value={ed.responsable}
                        onChange={(e) => setEd({ ...ed, responsable: e.target.value })}
                        className="mt-1.5 w-full px-3 py-2 text-sm">
                  <option value="">Sin asignar</option>
                  {usuarios.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.nombre ?? u.usuario} ({u.rol.toLowerCase()})
                    </option>
                  ))}
                </select>
                <span className="mt-1 block text-xs text-tinta-suave">
                  Es quien lo ve y quien firma el papel.
                </span>
              </label>
              <label className="block">
                <span className="rotulo">Estado</span>
                <select value={ed.estado}
                        onChange={(e) => setEd({ ...ed, estado: e.target.value })}
                        className="mt-1.5 w-full px-3 py-2 text-sm">
                  <option value="ABIERTO">Abierto</option>
                  <option value="CERRADO">Cerrado</option>
                </select>
              </label>
            </div>

            <label className="block">
              <span className="rotulo">Fecha de corte</span>
              <input type="date" value={ed.fecha_corte}
                     onChange={(e) => cambiarCorte(e.target.value)}
                     className="cifra mt-1.5 w-full px-3 py-2 text-sm" />
              <span className="mt-1 block text-xs text-tinta-suave">
                Al cambiarla se recalculan las dos comparativas de abajo.
              </span>
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="rotulo">Clases 1·2·3 contra</span>
                <input type="date" value={ed.fecha_cierre_anterior}
                       onChange={(e) => setEd({ ...ed, fecha_cierre_anterior: e.target.value })}
                       className="cifra mt-1.5 w-full px-3 py-2 text-sm" />
              </label>
              <label className="block">
                <span className="rotulo">Clases 4·5·6·7 contra</span>
                <input type="date" value={ed.fecha_corte_anterior}
                       onChange={(e) => setEd({ ...ed, fecha_corte_anterior: e.target.value })}
                       className="cifra mt-1.5 w-full px-3 py-2 text-sm" />
              </label>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            {choque ? (
              <button onClick={() => guardarEdicion(true)}
                      className="btn bg-rojo text-papel-alto hover:bg-rojo-vivo">
                Entiendo, cambiar de todos modos
              </button>
            ) : (
              <Boton onClick={() => guardarEdicion(false)}
                     disabled={!ed.razon_social.trim() || !ed.fecha_corte}>
                Guardar
              </Boton>
            )}
            <Boton variante="texto"
                   onClick={() => { setEditando(null); setChoque(null); }}>
              Cancelar
            </Boton>
          </div>
        </Modal>
      )}

    </div>
  );
}
