import { useEffect, useState } from "react";
import { api, cuandoExpireSesion } from "./api";
import Encargos from "./vistas/Encargos";
import Encargo from "./vistas/Encargo";
import Login from "./vistas/Login";
import Usuarios from "./vistas/Usuarios";
import Bitacora from "./vistas/Bitacora";
import { Boton, Chip } from "./comp/Piezas";

export default function App() {
  const [yo, setYo] = useState(null);
  const [verificando, setVerificando] = useState(true);
  const [encargoId, setEncargoId] = useState(null);
  const [vista, setVista] = useState("encargos");

  /* Al cargar se pregunta si la cookie sigue viva, en vez de asumir que
     hay que entrar: así recargar la página no obliga a re-autenticarse. */
  useEffect(() => {
    api.yo()
      .then(setYo)
      .catch(() => setYo(null))
      .finally(() => setVerificando(false));
  }, []);

  /* Si una sesión vence con la pestaña abierta, cualquier 401 devuelve al
     login en vez de dejar la pantalla llenándose de errores. */
  useEffect(() => {
    cuandoExpireSesion(() => { setYo(null); setEncargoId(null); });
  }, []);

  async function salir() {
    try { await api.logout(); } catch { /* la sesión igual se abandona */ }
    setYo(null);
    setEncargoId(null);
    setVista("encargos");
  }

  if (verificando) return null;              // evita el parpadeo del login
  if (!yo) return <Login onEntrar={setYo} />;

  return (
    <>
      {/* Los colores del anillo del logotipo, como firma de la marca */}
      <div className="cinta-marca sticky top-0 z-20" />
      <div className="sticky top-[3px] z-10 border-b border-regla
                      bg-papel-alto/85 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-6 py-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-full
                           bg-marca text-xs font-bold text-papel-alto">
            {yo.nombre.trim().charAt(0).toUpperCase()}
          </span>
          <span className="text-sm font-semibold">{yo.nombre}</span>
          {yo.rol === "ADMIN" && <Chip tono="morado">admin</Chip>}
          <div className="ml-auto flex items-center gap-3">
            {yo.rol === "ADMIN" && (
              <>
                <button onClick={() => setVista("bitacora")}
                        className={`pestana ${vista === "bitacora" ? "pestana-activa" : ""}`}>
                  Bitácora
                </button>
                <button onClick={() => setVista("usuarios")}
                        className={`pestana ${vista === "usuarios" ? "pestana-activa" : ""}`}>
                  Usuarios
                </button>
              </>
            )}
            <Boton variante="texto" onClick={salir}>Salir</Boton>
          </div>
        </div>
      </div>

      {vista === "bitacora"
        ? <Bitacora onVolver={() => setVista("encargos")} />
        : vista === "usuarios"
        ? <Usuarios yo={yo} onVolver={() => setVista("encargos")} />
        : encargoId
          ? <Encargo encargoId={encargoId} onVolver={() => setEncargoId(null)} />
          : <Encargos yo={yo} onAbrir={setEncargoId} />}
    </>
  );
}
