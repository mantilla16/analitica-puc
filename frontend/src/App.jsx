import { useEffect, useState } from "react";
import { api, cuandoExpireSesion } from "./api";
import Encargos from "./vistas/Encargos";
import Encargo from "./vistas/Encargo";
import Login from "./vistas/Login";
import Usuarios from "./vistas/Usuarios";
import Bitacora from "./vistas/Bitacora";
import { Anillo } from "./comp/Piezas";
import MenuUsuario from "./comp/MenuUsuario";

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
      <div className="cinta-marca sticky top-0 z-30" />
      <header className="sticky top-[3px] z-20 border-b border-regla
                         bg-papel-alto/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-6 py-2">
          {/* La marca ancla el encabezado a la izquierda y sirve de
              regreso al inicio; antes el lado izquierdo estaba vacío y
              todo el peso caía en tres botones sueltos a la derecha. */}
          <button onClick={() => { setVista("encargos"); setEncargoId(null); }}
                  className="flex items-center gap-2.5 rounded-full px-1 py-1
                             transition-colors hover:opacity-80">
            <Anillo tam={26} grosor={18} />
            <span className="text-sm font-bold tracking-tight">Russell Bedford</span>
            <span className="rotulo hidden sm:inline">Analítica</span>
          </button>

          <div className="ml-auto">
            <MenuUsuario yo={yo} vista={vista} onIr={setVista} onSalir={salir} />
          </div>
        </div>
      </header>

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
