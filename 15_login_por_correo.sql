-- =====================================================================
-- INGRESO POR CORREO DE DOMINIO + CÓDIGO DE 6 DÍGITOS
--
-- Se acaban las contraseñas. Para entrar se escribe el correo @rbcol.co,
-- llega un código de 6 dígitos y con eso se abre la sesión. La primera
-- vez, después de probar que controla el buzón, la persona completa sus
-- datos y queda registrada.
--
-- Por qué el correo es la identidad y no el nombre de usuario: en un
-- papel de trabajo hay que poder demostrar QUIÉN hizo cada cosa, y un
-- buzón de dominio lo respalda un tercero (el directorio de la firma).
-- Un usuario y una contraseña los puede compartir cualquiera sin que
-- quede rastro.
--
-- `correo` NO se declara NOT NULL: hay usuarios creados antes de esto
-- que no tienen correo, y inventarles uno seria peor que dejarlos sin
-- entrar. Quien no tenga correo simplemente no puede ingresar hasta que
-- se le asigne con `python usuarios.py correo <usuario> <correo>`. La
-- unicidad si se exige, sobre el correo en minusculas.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 15_login_por_correo.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

-- ------------------------------------------------------------------ 1
-- El usuario: correo como identidad, datos del registro, sin clave
-- ------------------------------------------------------------------

ALTER TABLE core.usuario
  ALTER COLUMN clave_hash DROP NOT NULL,
  ADD COLUMN IF NOT EXISTS cargo                text,
  ADD COLUMN IF NOT EXISTS tarjeta_profesional  text,
  ADD COLUMN IF NOT EXISTS telefono             text,
  ADD COLUMN IF NOT EXISTS registrado_en        timestamptz;

COMMENT ON COLUMN core.usuario.clave_hash IS
  'Sin uso desde el ingreso por correo. Se conserva para no perder el
   dato de cuentas antiguas; nada lo lee.';
COMMENT ON COLUMN core.usuario.registrado_en IS
  'Cuándo completó sus datos. NULL = probó su buzón pero no ha llenado el
   formulario; con NULL solo puede llegar a /auth/registro.';
COMMENT ON COLUMN core.usuario.tarjeta_profesional IS
  'Número de tarjeta profesional del contador. Es con lo que se firma un
   dictamen en Colombia, así que el papel lo necesita.';

-- Un mismo buzón no puede ser dos cuentas. En minúsculas porque el
-- correo no distingue mayúsculas y "A.Mantilla@" no es otra persona.
CREATE UNIQUE INDEX IF NOT EXISTS ux_usuario_correo
  ON core.usuario (lower(correo)) WHERE correo IS NOT NULL;

-- Las cuentas que ya existen quedan registradas: sus datos los puso un
-- administrador, no hay que volver a pedírselos.
UPDATE core.usuario SET registrado_en = creado_en WHERE registrado_en IS NULL;

-- ------------------------------------------------------------------ 2
-- Los códigos de acceso
-- ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS core.codigo_acceso (
  id           bigserial PRIMARY KEY,
  correo       text        NOT NULL,
  codigo_hash  text        NOT NULL,
  creado_en    timestamptz NOT NULL DEFAULT now(),
  expira_en    timestamptz NOT NULL,
  intentos     integer     NOT NULL DEFAULT 0,
  usado_en     timestamptz,
  ip           text,
  agente       text
);

COMMENT ON TABLE core.codigo_acceso IS
  'Códigos de un solo uso. Se guarda el hash scrypt, no el código: quien
   lea la tabla no puede entrar con lo que ve.';
COMMENT ON COLUMN core.codigo_acceso.intentos IS
  'Verificaciones falladas contra este código. Seis dígitos son un millón
   de combinaciones, poco para resistir un tanteo: el límite de intentos
   es lo que de verdad lo protege, no su longitud.';
COMMENT ON COLUMN core.codigo_acceso.usado_en IS
  'Marca de consumo. Un código sirve UNA vez: si se reusara, quien vea el
   correo por encima del hombro entra después.';

CREATE INDEX IF NOT EXISTS ix_codigo_correo
  ON core.codigo_acceso (lower(correo), creado_en DESC);

-- ------------------------------------------------------------------ 3
-- El encargo tiene dueño
-- ------------------------------------------------------------------

ALTER TABLE core.encargo
  ADD COLUMN IF NOT EXISTS creado_por uuid REFERENCES core.usuario(id);

COMMENT ON COLUMN core.encargo.creado_por IS
  'Quién lo creó. Es la base de la visibilidad: un AUDITOR solo ve los
   suyos, un ADMIN ve todos. NULL solo lo ve un ADMIN -- ocultarle un
   encargo a todo el mundo por no saber de quién es seria perderlo.';

-- Se rellena desde `responsable`, que hasta hoy era el nombre de usuario
-- escogido de la lista de auditores activos.
UPDATE core.encargo e
   SET creado_por = u.id
  FROM core.usuario u
 WHERE e.creado_por IS NULL
   AND e.responsable IS NOT NULL
   AND lower(u.usuario) = lower(e.responsable);

CREATE INDEX IF NOT EXISTS ix_encargo_creado_por
  ON core.encargo (creado_por);

COMMIT;


-- =====================================================================
-- VERIFICACIÓN
-- =====================================================================

\echo '--- usuarios: quién puede entrar y quién no'
SELECT usuario, rol, activo,
       coalesce(correo, '(SIN CORREO: no puede entrar)') AS correo,
       (registrado_en IS NOT NULL) AS registrado
FROM core.usuario ORDER BY usuario;

\echo '--- encargos: dueño asignado'
SELECT cl.razon_social, e.fecha_corte, e.responsable,
       coalesce(u.usuario, '(SIN DUEÑO: solo lo ve un ADMIN)') AS creado_por
FROM core.encargo e
JOIN core.cliente cl ON cl.id = e.cliente_id
LEFT JOIN core.usuario u ON u.id = e.creado_por
ORDER BY cl.razon_social, e.fecha_corte;

\echo '--- resumen'
SELECT count(*) FILTER (WHERE creado_por IS NULL) AS encargos_sin_dueno,
       count(*)                                   AS encargos_totales
FROM core.encargo;
