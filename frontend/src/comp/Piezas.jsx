import { monto, entero } from "../api";

/** El gesto del lápiz sobre la cifra verificada. */
export function Punteo({ tam = 18 }) {
  return (
    <svg className="punteo" width={tam} height={tam} viewBox="0 0 24 24" fill="none"
         aria-hidden="true">
      <path d="M4 13.5 L9.5 19 L20 5" stroke="var(--color-verde)" strokeWidth="2.5"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Boton({ children, variante = "principal", className = "", ...props }) {
  const estilos = {
    principal: "btn-principal",
    contorno: "btn-contorno",
    texto: "btn-texto",
  };
  // La clase que llegue se suma, no reemplaza: si se dejara pasar por
  // props, React se quedaría solo con ella y el botón perdería su estilo.
  return (
    <button className={`btn ${estilos[variante]} ${className}`} {...props}>
      {children}
    </button>
  );
}

/** El anillo del logotipo, dibujado. Cuatro arcos con los colores de la
 *  marca; se usa como elemento gráfico, no como logo oficial. */
export function Anillo({ tam = 320, grosor = 10, className = "" }) {
  const r = 100;
  const c = 2 * Math.PI * r;              // 628.3
  const tramo = c / 4 - 8;                // deja un respiro entre arcos
  const arcos = [
    ["var(--color-cian)", 0],
    ["var(--color-naranja)", -c / 4],
    ["var(--color-cian)", -c / 2],
    ["var(--color-morado)", (-c * 3) / 4],
  ];
  return (
    <svg viewBox="0 0 240 240" width={tam} height={tam} className={className}
         fill="none" aria-hidden="true">
      <g transform="rotate(-90 120 120)">
        {arcos.map(([color, desfase], i) => (
          <circle key={i} cx="120" cy="120" r={r} stroke={color}
                  strokeWidth={grosor} strokeLinecap="round"
                  strokeDasharray={`${tramo} ${c - tramo}`}
                  strokeDashoffset={desfase} />
        ))}
      </g>
    </svg>
  );
}

/** Etiqueta de estado. Un color plano dice más rápido que una palabra
 *  suelta si algo está bien, mal o pendiente. */
export function Chip({ tono = "gris", children }) {
  return <span className={`chip chip-${tono}`}>{children}</span>;
}

export function Aviso({ tono = "info", titulo, children }) {
  const tonos = {
    ok: "border-verde bg-verde-tenue text-verde",
    error: "border-rojo bg-rojo-tenue text-rojo",
    alerta: "border-ambar bg-ambar-tenue text-ambar",
    info: "border-regla bg-papel-hondo text-tinta-media",
  };
  // El distintivo lleva color propio en vez de una opacidad sobre
  // currentColor: menos elegante de escribir, pero no depende de cómo
  // resuelva Tailwind los modificadores de opacidad sobre `current`.
  const insignias = {
    ok: "bg-verde text-papel-alto",
    error: "bg-rojo text-papel-alto",
    alerta: "bg-ambar text-papel-alto",
    info: "bg-tinta-suave text-papel-alto",
  };
  const iconos = { ok: "✓", error: "!", alerta: "!", info: "i" };
  return (
    <div className={`flex gap-3 rounded-[12px] border-l-4 px-4 py-3.5 text-sm ${tonos[tono]}`}>
      <span className={`mt-px flex h-5 w-5 shrink-0 items-center justify-center
                        rounded-full text-xs font-bold ${insignias[tono]}`}>
        {iconos[tono]}
      </span>
      <div className="min-w-0">
        {titulo && <p className="mb-0.5 font-semibold">{titulo}</p>}
        <div className="leading-relaxed">{children}</div>
      </div>
    </div>
  );
}

/**
 * La tira de cuadre. Elemento central de la aplicación.
 *
 * Cada nivel completo del balance debe sumar cero por sí solo: es la
 * ecuación contable. Cuando lo hace, aparece el punteo.
 * Auxiliar no cuadra solo porque hay subcuentas que no bajan a 8 dígitos.
 */
export function Cuadre({ cuadre }) {
  if (!cuadre?.length) return null;
  return (
    <div>
      <p className="rotulo mb-3">Cuadre por nivel</p>
      <div className="border-t border-regla">
        {cuadre.map((n) => {
          const ok = n.estado === "OK";
          const roto = n.estado === "DESCUADRE";
          return (
            <div key={n.nivel}
                 className="flex items-baseline gap-4 border-b border-regla-fina py-3">
              <span className="w-28 text-sm font-medium">{n.nivel}</span>
              <span className="cifra w-16 text-xs text-tinta-suave">
                {entero(n.filas)}
              </span>
              <span
                className={`cifra flex-1 text-right text-lg ${
                  ok ? "text-verde" : roto ? "text-rojo" : "text-tinta-suave"
                }`}
              >
                {monto(n.suma_saldo_final)}
              </span>
              <span className="flex w-28 items-center justify-end gap-1.5">
                {ok && <Punteo />}
                {roto && <Chip tono="rojo">descuadre</Chip>}
                {!n.nivel_completo && (
                  <span title="Nivel incompleto: hay subcuentas que no bajan a este nivel">
                    <Chip tono="gris">parcial</Chip>
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-xs text-tinta-suave leading-relaxed">
        Cada nivel completo es el mismo balance, solo más desglosado. Por eso
        debe sumar cero por sí solo.
      </p>
    </div>
  );
}

export function Dato({ etiqueta, children, ancho = "" }) {
  return (
    <div className={ancho}>
      <p className="rotulo mb-1">{etiqueta}</p>
      <p className="text-sm">{children}</p>
    </div>
  );
}
