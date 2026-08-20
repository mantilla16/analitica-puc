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

export function Boton({ children, variante = "principal", ...props }) {
  const base =
    "inline-flex items-center gap-2 px-4 py-2 text-sm font-medium " +
    "transition-colors disabled:opacity-40 disabled:cursor-not-allowed";
  const estilos = {
    principal: "bg-verde text-papel hover:bg-tinta",
    contorno: "border border-regla text-tinta hover:bg-papel-hondo",
    texto: "text-tinta-media hover:text-tinta underline underline-offset-4",
  };
  return (
    <button className={`${base} ${estilos[variante]}`} {...props}>
      {children}
    </button>
  );
}

export function Aviso({ tono = "info", titulo, children }) {
  const tonos = {
    ok: "border-verde bg-verde-tenue text-verde",
    error: "border-rojo bg-rojo-tenue text-rojo",
    alerta: "border-ambar bg-ambar-tenue text-ambar",
    info: "border-regla bg-papel-hondo text-tinta-media",
  };
  return (
    <div className={`border-l-2 px-4 py-3 text-sm ${tonos[tono]}`}>
      {titulo && <p className="font-semibold mb-0.5">{titulo}</p>}
      <div className="leading-relaxed">{children}</div>
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
              <span className="flex w-24 items-center justify-end gap-1.5">
                {ok && <Punteo />}
                {roto && (
                  <span className="rotulo text-rojo">descuadre</span>
                )}
                {!n.nivel_completo && (
                  <span className="rotulo" title="Nivel incompleto: hay subcuentas que no bajan a este nivel">
                    parcial
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
