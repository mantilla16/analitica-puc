import { useEffect, useState } from "react";
import { api, monto } from "../api";
import { Aviso, Boton, Punteo } from "../comp/Piezas";

const AYUDA = {
  PLANEACION:
    "Se fija al planear el trabajo. Es la referencia de la que suelen derivarse las demás.",
  EJECUCION:
    "Performance materiality. Más baja que la de planeación para dejar margen a la acumulación de hallazgos pequeños.",
  CIERRE:
    "Se revisa al concluir, cuando ya se conocen las cifras definitivas.",
};

// Rangos permitidos del % sobre la global. El backend los valida de verdad
// (responde 422); acá solo se avisa antes de enviar.
const RANGO = { desempeno: [20, 90], trivial: [2, 10] };

const aNum = (v) => (v === "" || v === null || v === undefined ? null : Number(v));
const redondea = (n, d = 2) => Math.round(n * 10 ** d) / 10 ** d;
const pctFmt = (n) => n.toLocaleString("es-CO", { maximumFractionDigits: 2 });

/** Estado editable de una cifra derivada (desempeño o trivial). */
function inicial(c, modoPorDefecto) {
  return {
    modo: c?.modo ?? modoPorDefecto,
    pct: c?.pct ?? "",
    valor: c?.valor ?? "",
  };
}

/**
 * Lo que el auditor digitó manda; la otra forma de la cifra se deriva en
 * vivo desde la global del borrador.
 */
function derivar(c, glob) {
  const g = aNum(glob);
  if (c.modo === "PCT") {
    const p = aNum(c.pct);
    return { pct: p, valor: p !== null && g ? (g * p) / 100 : null };
  }
  const v = aNum(c.valor);
  return { valor: v, pct: v !== null && g ? (v / g) * 100 : null };
}

/**
 * Un bloque de desempeño o trivial: selector de modo, input y la cifra
 * derivada en gris. Si el % queda fuera de rango el input se pinta en rojo.
 */
function CifraDerivada({ rotulo, rango, c, glob, onCambio, fuera }) {
  const d = derivar(c, glob);
  const [min, max] = rango;

  const cambiarModo = (modo) => {
    if (modo === c.modo) return;
    // Al cambiar de modo se arrastra la cifra derivada para no perder lo digitado.
    onCambio({
      ...c, modo,
      pct: modo === "PCT" && d.pct !== null ? String(redondea(d.pct)) : c.pct,
      valor: modo === "VALOR" && d.valor !== null ? String(redondea(d.valor)) : c.valor,
    });
  };

  return (
    <div>
      <div className="flex items-center gap-2">
        <span className="rotulo">{rotulo}</span>
        <div className="flex gap-1">
          {[["PCT", "%"], ["VALOR", "Pesos"]].map(([m, t]) => (
            <button key={m} type="button" onClick={() => cambiarModo(m)}
                    className={`chip-filtro ${c.modo === m ? "chip-filtro-activo" : ""}`}>
              {t}
            </button>
          ))}
        </div>
      </div>

      <input
        type="number" step="0.01"
        value={c.modo === "PCT" ? c.pct : c.valor}
        onChange={(e) => onCambio({ ...c, [c.modo === "PCT" ? "pct" : "valor"]: e.target.value })}
        placeholder="0"
        className={`cifra mt-1 w-48 border bg-papel px-3 py-2 text-sm ${
          fuera ? "border-rojo text-rojo" : "border-regla"}`}
      />

      <p className="mt-1 text-xs text-tinta-suave">
        {c.modo === "PCT"
          ? (d.valor !== null ? `= ${monto(d.valor)}` : "= —")
          : (d.pct !== null ? `= ${pctFmt(d.pct)} % de la global` : "= — % de la global")}
      </p>
      <p className={`text-xs ${fuera ? "text-rojo" : "text-tinta-suave"}`}>
        entre {min} y {max} %
      </p>
    </div>
  );
}

/**
 * Tres materialidades por fase (global, desempeño y trivial). La global la
 * digita el auditor; desempeño y trivial se expresan como % o como valor y
 * la otra forma se deriva. El sistema no inventa ninguna cifra.
 */
export default function Materialidad({ encargoId, onCambio }) {
  const [d, setD] = useState(null);
  const [borrador, setBorrador] = useState({});
  const [param, setParam] = useState({
    pct_variacion: "20",
    aplica_variacion: true, aplica_trivialidad: true,
  });
  const [error, setError] = useState(null);
  const [guardado, setGuardado] = useState(null);

  useEffect(() => { cargar(); }, [encargoId]);

  async function cargar() {
    try {
      const r = await api.materialidades(encargoId);
      setD(r);
      const b = {};
      (r.materialidades ?? []).forEach((m) => {
        b[m.fase] = {
          // `valor` era el nombre anterior de la global.
          global: m.global ?? m.valor ?? "",
          porcentaje: m.porcentaje ?? "",
          aplicar: m.aplicar,
          des: inicial(m.desempeno, "PCT"),
          tri: inicial(m.trivial, "PCT"),
        };
      });
      setBorrador(b);
      setParam({
        pct_variacion: String(r.pct_variacion ?? 20),
        aplica_variacion: r.aplica_variacion ?? true,
        aplica_trivialidad: r.aplica_trivialidad ?? true,
      });
    } catch (e) { setError(e.message); }
  }

  // El error de un guardado (422) se muestra arriba sin ocultar el formulario;
  // solo un fallo de la carga inicial lo reemplaza.
  if (!d && error) return <Aviso tono="error">{error}</Aviso>;
  if (!d) return <p className="text-sm text-tinta-suave">Cargando…</p>;

  const editar = (fase, campo, v) =>
    setBorrador({ ...borrador, [fase]: { ...borrador[fase], [campo]: v } });

  // Fuera de rango = hay % (digitado o derivado) y no cae en el intervalo.
  const fueraDeRango = (c, glob, [min, max]) => {
    const p = derivar(c, glob).pct;
    return p !== null && (p < min || p > max);
  };

  const cuerpoCifra = (c) =>
    c.modo === "PCT"
      ? { modo: "PCT", pct: aNum(c.pct) }
      : { modo: "VALOR", valor: aNum(c.valor) };

  async function guardar(fase) {
    setError(null);
    const b = borrador[fase];
    try {
      await api.guardarMaterialidad(encargoId, fase, {
        global: aNum(b.global),
        aplicar: b.aplicar,
        porcentaje: aNum(b.porcentaje),
        desempeno: cuerpoCifra(b.des),
        trivial: cuerpoCifra(b.tri),
      });
      setGuardado(fase);
      setTimeout(() => setGuardado(null), 2000);
      await cargar();
      onCambio?.();
    } catch (e) { setError(e.message); }
  }

  async function guardarParametros() {
    setError(null);
    try {
      await api.guardarParametros(encargoId, {
        pct_variacion: Number(param.pct_variacion),
        aplica_variacion: param.aplica_variacion,
        aplica_trivialidad: param.aplica_trivialidad,
      });
      await cargar();
      onCambio?.();
    } catch (e) { setError(e.message); }
  }

  async function activar(fase) {
    await api.fijarFase(encargoId, fase);
    await cargar();
    onCambio?.();
  }

  return (
    <div className="space-y-10">
      <div>
        <p className="rotulo mb-1">Materialidad por fase</p>
        <p className="max-w-2xl text-sm text-tinta-media">
          El ejercicio se corre en tres fases. Cada una tiene tres cifras: la
          materialidad <strong>global</strong>, la de <strong>desempeño</strong>{" "}
          (umbral de selección por monto) y la <strong>trivial</strong> (error
          trivial de los criterios). Usted decide cuáles fases aplicar; el
          sistema no calcula la global.
        </p>
      </div>

      {error && <Aviso tono="error">{error}</Aviso>}

      <div className="space-y-px bg-regla">
        {d.materialidades.map((m) => {
          const b = borrador[m.fase];
          if (!b) return null;
          const activa = d.fase_activa === m.fase;
          const desFuera = fueraDeRango(b.des, b.global, RANGO.desempeno);
          const triFuera = fueraDeRango(b.tri, b.global, RANGO.trivial);

          return (
            <div key={m.fase}
                 className={`bg-papel-alto p-5 ${activa ? "border-l-2 border-verde" : "border-l-2 border-transparent"}`}>
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <span className="rotulo">{m.fase_nombre}</span>
                <span className="font-medium">{m.nombre}</span>
                {activa && (
                  <span className="rotulo flex items-center gap-1 text-verde">
                    <Punteo tam={13} /> fase en curso
                  </span>
                )}
                {!activa && (
                  <button onClick={() => activar(m.fase)}
                          className="rotulo hover:text-tinta">
                    usar esta fase
                  </button>
                )}
                {guardado === m.fase && (
                  <span className="rotulo text-verde">guardado</span>
                )}
              </div>

              <p className="mb-4 max-w-2xl text-xs leading-relaxed text-tinta-suave">
                {AYUDA[m.fase]}
              </p>

              <div className="grid gap-6 sm:grid-cols-3">
                <label className="block">
                  <span className="rotulo">Global · pesos</span>
                  <input
                    type="number" step="0.01" value={b.global}
                    onChange={(e) => editar(m.fase, "global", e.target.value)}
                    placeholder="0"
                    className="cifra mt-1 w-48 border border-regla bg-papel px-3 py-2 text-sm"
                  />
                  <span className="mt-1 block text-xs text-tinta-suave">
                    la digita el auditor
                  </span>
                </label>

                <CifraDerivada rotulo="Desempeño" rango={RANGO.desempeno}
                               c={b.des} glob={b.global} fuera={desFuera}
                               onCambio={(v) => editar(m.fase, "des", v)} />

                <CifraDerivada rotulo="Trivial" rango={RANGO.trivial}
                               c={b.tri} glob={b.global} fuera={triFuera}
                               onCambio={(v) => editar(m.fase, "tri", v)} />
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-5">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={b.aplicar ?? false}
                         onChange={(e) => editar(m.fase, "aplicar", e.target.checked)} />
                  Aplicar
                </label>

                <Boton variante="contorno" onClick={() => guardar(m.fase)}
                       disabled={desFuera || triFuera}>
                  Guardar
                </Boton>
                {(desFuera || triFuera) && (
                  <span className="text-xs text-rojo">
                    Un porcentaje está fuera del rango permitido.
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* --------------------------------------------- criterios de selección */}
      <div className="border-t border-regla pt-6">
        <p className="rotulo mb-1">Criterios de selección</p>
        <p className="mb-4 max-w-2xl text-sm text-tinta-media">
          Aplican sobre las materialidades de la fase en curso.
        </p>

        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex w-52 items-center gap-2 text-sm">
              <input type="checkbox" checked={param.aplica_variacion}
                     onChange={(e) => setParam({ ...param, aplica_variacion: e.target.checked })} />
              Variación porcentual
            </label>
            <div className="flex items-center gap-2">
              <input type="number" step="0.01" value={param.pct_variacion}
                     disabled={!param.aplica_variacion}
                     onChange={(e) => setParam({ ...param, pct_variacion: e.target.value })}
                     className="cifra w-24 border border-regla bg-papel px-3 py-2 text-sm disabled:opacity-40" />
              <span className="text-sm text-tinta-suave">
                % en cualquier sentido, positivo o negativo
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <label className="flex w-52 items-center gap-2 text-sm">
              <input type="checkbox" checked={param.aplica_trivialidad}
                     onChange={(e) => setParam({ ...param, aplica_trivialidad: e.target.checked })} />
              Error trivial
            </label>
            <span className="text-sm text-tinta-suave">
              usa la materialidad trivial de la fase en curso
            </span>
          </div>

          <Boton variante="contorno" onClick={guardarParametros}>Guardar</Boton>
        </div>

        <div className="mt-5 max-w-2xl space-y-2 text-xs leading-relaxed text-tinta-suave">
          <p>
            Una cuenta se marca si su variación supera la materialidad de{" "}
            <strong className="text-tinta-media">desempeño</strong> de la fase en
            curso, o por alguno de los criterios estructurales: apareció,
            desapareció, o quedó con saldo contrario a su naturaleza.
          </p>
          <p>
            <strong className="text-tinta-media">Variación porcentual</strong> agrega
            las que se movieron más del porcentaje indicado, en cualquier sentido.
            Apagarlo deja la selección apoyada solo en la materialidad de
            desempeño y en los criterios estructurales.
          </p>
          <p>
            <strong className="text-tinta-media">Error trivial</strong> descarta lo
            pequeño en esos criterios, usando la materialidad trivial de la fase.
            Sin él, una cuenta que pasa de 2 a 10 millones entra como “+400%”.
            Apagarlo vuelve el criterio de porcentaje absoluto: cualquier cuenta
            que cruce el porcentaje se reporta, sin importar la cifra.
          </p>
          {!param.aplica_variacion && !param.aplica_trivialidad && (
            <p className="text-ambar">
              Con ambos apagados solo quedan la materialidad de desempeño y los
              criterios estructurales.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
