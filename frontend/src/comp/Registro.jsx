import { useState } from "react";
import { api } from "../api";
import { Aviso, Boton, Modal } from "./Piezas";

/**
 * Lo que se pide la primera vez que alguien entra.
 *
 * Aparece cuando el servidor dice `registro_pendiente`, y no se puede
 * cerrar: mientras el registro no esté completo el middleware rechaza
 * todo lo demás, así que un botón de "más tarde" solo llevaría a una
 * aplicación que responde 403 a todo sin explicar por qué.
 *
 * Se piden pocos campos y todos tienen un uso concreto en el papel de
 * trabajo. Un formulario que pide datos "por si acaso" se llena de
 * cualquier manera, y después esos datos se citan como si fueran ciertos.
 */
export default function Registro({ correo, onListo }) {
  const [d, setD] = useState({
    nombre: "", cargo: "", tarjeta_profesional: "", telefono: "",
  });
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);

  const puedeGuardar = d.nombre.trim().split(/\s+/).length >= 2;

  async function guardar(e) {
    e.preventDefault();
    setError(null);
    setOcupado(true);
    try {
      onListo(await api.registrarme(d));
    } catch (err) {
      setError(err.message);
    } finally {
      setOcupado(false);
    }
  }

  const campo = "w-full px-3 py-2 text-sm";
  const set = (k) => (e) => setD({ ...d, [k]: e.target.value });

  return (
    <Modal titulo="Complete su registro" rotulo="Primera vez"
           ancho="max-w-md" onCerrar={null}>
      <p className="text-sm leading-relaxed text-tinta-media">
        Confirmamos que <span className="cifra">{correo}</span> es suyo.
        Estos datos quedan en los papeles de trabajo que usted elabore,
        así que van como los firmaría.
      </p>

      {error && <div className="mt-4"><Aviso tono="error">{error}</Aviso></div>}

      <form onSubmit={guardar} className="mt-5 space-y-4">
        <label className="block">
          <span className="rotulo">Nombre y apellidos</span>
          <input value={d.nombre} onChange={set("nombre")} required autoFocus
                 autoComplete="name" className={`${campo} mt-1.5`} />
        </label>

        <label className="block">
          <span className="rotulo">Cargo</span>
          <input value={d.cargo} onChange={set("cargo")}
                 placeholder="Auditor senior, revisor fiscal…"
                 className={`${campo} mt-1.5`} />
          <span className="mt-1 block text-xs text-tinta-suave">
            Opcional.
          </span>
        </label>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="rotulo">Tarjeta profesional</span>
            <input value={d.tarjeta_profesional}
                   onChange={set("tarjeta_profesional")}
                   className={`${campo} mt-1.5 cifra`} />
            <span className="mt-1 block text-xs leading-snug text-tinta-suave">
              Con esto se firma un dictamen. Opcional, pero si la tiene
              conviene dejarla.
            </span>
          </label>

          <label className="block">
            <span className="rotulo">Teléfono</span>
            <input value={d.telefono} onChange={set("telefono")}
                   inputMode="tel" className={`${campo} mt-1.5 cifra`} />
            <span className="mt-1 block text-xs text-tinta-suave">
              Opcional.
            </span>
          </label>
        </div>

        <Boton type="submit" disabled={ocupado || !puedeGuardar}
               className="w-full justify-center">
          {ocupado ? "Guardando…" : "Guardar y continuar"}
        </Boton>
        {!puedeGuardar && d.nombre.trim() !== "" && (
          <p className="text-xs text-tinta-suave">
            Escriba nombre y apellidos.
          </p>
        )}
      </form>
    </Modal>
  );
}
