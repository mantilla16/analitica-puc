/**
 * Inicio de sesión con Microsoft Entra ID.
 *
 * La configuración -- id de cliente e id de inquilino -- la entrega el
 * backend en /api/auth/estado, no está escrita aquí: así el mismo bundle
 * sirve para desarrollo y producción, y cambiar de inquilino no obliga a
 * recompilar.
 *
 * MSAL se carga bajo demanda (import dinámico) para que no entre en el
 * bundle inicial de quien ya tiene la sesión abierta.
 *
 * Los cinco estados del flujo, para tenerlos juntos:
 *
 *   1. Carga normal, sin fragmento en la URL
 *      No hay nada que completar. Se muestra el botón.
 *
 *   2. Clic en el botón
 *      `signIn` redirige a Microsoft. La página se abandona; no retorna.
 *
 *   3. Vuelta con éxito (#code=...)
 *      `completeRedirect` canjea el código, devuelve el id_token y limpia
 *      el fragmento. Solo puede ocurrir UNA vez por carga de página.
 *
 *   4. Vuelta con error (#error=...)
 *      Igual que 3, pero `handleRedirectPromise` lanza. Se traduce el error
 *      y se limpia el fragmento para que una recarga no lo repita.
 *
 *   5. Cierre de sesión
 *      NO recarga la página, así que este módulo sigue vivo con su estado.
 *      Hay que invalidar la redirección pendiente y borrar la caché, o el
 *      siguiente montaje de la pantalla de acceso vuelve a entrar solo.
 */

let instance = null;
let loading = null;
let configuracion = null;

/* Se mira el fragmento UNA vez, al cargar el módulo. Sin esto,
   `handleRedirectPromise` devuelve el resultado cacheado del login anterior
   y vuelve a iniciar sesión justo después de cerrarla. */
const VIENE_DE_MICROSOFT =
  typeof window !== "undefined" && /[#&](code|error|id_token|state)=/.test(window.location.hash);

let redireccionConsumida = false;

async function getInstance({ msClientId, msTenantId }) {
  if (instance) return instance;
  if (loading) return loading;

  loading = (async () => {
    const { PublicClientApplication } = await import("@azure/msal-browser");
    const app = new PublicClientApplication({
      auth: {
        clientId: msClientId,
        authority: `https://login.microsoftonline.com/${msTenantId}`,
        redirectUri: window.location.origin + import.meta.env.BASE_URL,
      },
      cache: {
        // localStorage: el estado del intercambio sobrevive a la ida y
        // vuelta a Microsoft aunque el navegador restaure la pestaña.
        cacheLocation: "localStorage",
        storeAuthStateInCookie: false,
      },
    });
    await app.initialize();
    instance = app;
    configuracion = { msClientId, msTenantId };
    return app;
  })();

  return loading;
}

const REQUEST = (config) => ({
  scopes: ["openid", "profile", "email"],
  prompt: "select_account",
  ...(config.allowedDomain ? { domainHint: config.allowedDomain } : {}),
});

/**
 * Lleva a la página de Microsoft. No retorna: la pestaña navega y el flujo
 * lo termina `completeRedirect` al volver.
 *
 * Se usa redirección y no popup a propósito: con `loginPopup` la aplicación
 * se cargaba dentro del popup, contexto distinto que no ve el
 * sessionStorage donde MSAL dejó el verificador PKCE, así que al intentar
 * canjear el código fallaba con `no_token_request_cache_error`. Además las
 * políticas de equipos corporativos suelen bloquear los popups.
 */
export async function signIn(config) {
  const app = await getInstance(config);
  await app.loginRedirect(REQUEST(config));
}

/** Termina el inicio al volver de Microsoft. null si es una carga normal. */
export async function completeRedirect(config) {
  if (!config?.msClientId || !config?.msTenantId) return null;
  if (redireccionConsumida) return null;
  redireccionConsumida = true;
  if (!VIENE_DE_MICROSOFT) return null;
  try {
    const app = await getInstance(config);
    const result = await app.handleRedirectPromise();
    return result?.idToken || null;
  } finally {
    limpiarFragmento();
  }
}

export function limpiarFragmento() {
  try {
    if (!window.location.hash) return;
    window.history.replaceState({}, "", window.location.pathname + window.location.search);
  } catch { /* sin history: no es crítico */ }
}

export async function signOut(config) {
  redireccionConsumida = true;
  const cfg = config?.msClientId ? config : configuracion;
  try {
    if (instance || cfg?.msClientId) {
      const app = await getInstance(cfg);
      await app.clearCache();
    }
  } catch { /* que falle limpieza no debe impedir cerrar sesión */ }
  limpiarFragmento();
  try {
    for (const k of Object.keys(window.localStorage)) {
      if (k.startsWith("msal.") || k.includes("login.microsoftonline.com")) {
        window.localStorage.removeItem(k);
      }
    }
  } catch { /* almacenamiento bloqueado */ }
}

/** Traduce errores de MSAL a algo que el usuario pueda accionar. */
export function describeError(err) {
  const code = err?.errorCode || "";
  if (code === "user_cancelled") return "Cancelaste el inicio de sesión.";
  if (code === "interaction_in_progress") {
    return "Ya hay un inicio de sesión en curso. Espera un momento o recarga la página.";
  }
  if (/AADSTS50011/.test(err?.message || "")) {
    return "La dirección de esta página no está registrada como URI de redirección en Azure. Agrégala en el registro de la aplicación (plataforma SPA).";
  }
  if (/AADSTS700016|AADSTS90002/.test(err?.message || "")) {
    return "El registro de la aplicación no existe en este inquilino. Revisa MS_CLIENT_ID y MS_TENANT_ID en el servidor.";
  }
  return err?.message || "No se pudo iniciar sesión con Microsoft.";
}
