import { useEffect, useState } from "react";
import { api, fecha } from "../api";
import { Aviso, Boton, Chip, Confirmar, Modal } from "../comp/Piezas";

export default function Encargos({ yo, onAbrir }) {
  const [lista, setLista] = useState([]);
  const [creando, setCreando] = useState(false);
  const [error, setError] = useState(null);
  const [borrando, setBorrando] = useState(null);   // encargo por confirmar
  const [asignando, setAsignando] = useState(null);
  const [usuarios, setUsuarios] = useState([]);
  const [destino, setDestino] = useState("");
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

  function abrirAsignacion(enc) {
    setAsignando(enc);
    setDestino(enc.creado_por ?? "");
  }

  async function reasignar() {
    if (!asignando || !destino) return;
    setError(null);
    try {
      await api.reasignarEncargo(asignando.id, destino);
      setAsignando(null);
      refrescar();
    } catch (err) {
      setError(err.message);
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
                      onClick={(ev) => { ev.stopPropagation(); abrirAsignacion(e); }}
                      className="rotulo shrink-0 text-tinta-suave hover:text-marca"
                      title="Cambiar el responsable del encargo"
                    >
                      Asignar
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

      {asignando && (
        <Modal titulo={`Asignar ${asignando.razon_social}`} rotulo="Administrador"
               onCerrar={() => setAsignando(null)}>
          <p className="text-sm leading-relaxed text-tinta-media">
            El usuario elegido verá este encargo y pasará a figurar como su
            responsable. El cambio queda registrado en la bitácora.
          </p>
          <label className="mt-5 block">
            <span className="rotulo">Responsable</span>
            <select value={destino} onChange={(e) => setDestino(e.target.value)}
                    className="mt-1.5 w-full px-3 py-2 text-sm">
              <option value="">Seleccione un usuario</option>
              {usuarios.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nombre ?? u.usuario} ({u.rol.toLowerCase()})
                </option>
              ))}
            </select>
          </label>
          <div className="mt-6 flex gap-3">
            <Boton onClick={reasignar} disabled={!destino}>Guardar asignación</Boton>
            <Boton variante="texto" onClick={() => setAsignando(null)}>Cancelar</Boton>
          </div>
        </Modal>
      )}
    </div>
  );
}
