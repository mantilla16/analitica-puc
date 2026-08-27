-- =====================================================================
-- USUARIOS Y SESIONES
--
-- La aplicación deja de ser abierta: todo /api exige sesión. Cada auditor
-- tiene su cuenta, y con eso los campos que hoy quedan vacíos o se
-- teclean a mano (subido_por, aprobado_por, creado_por) se llenan solos
-- con quien realmente hizo la acción -- que en un papel de trabajo es
-- justamente lo que se necesita poder demostrar.
--
-- Se guarda el HASH del token de sesión, no el token: si alguien lee la
-- tabla no puede suplantar una sesión viva.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 11_usuarios.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE core.usuario (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario        text NOT NULL UNIQUE,
  nombre         text NOT NULL,
  correo         text,
  clave_hash     text NOT NULL,
  rol            text NOT NULL DEFAULT 'AUDITOR',
  activo         boolean NOT NULL DEFAULT true,
  creado_en      timestamptz NOT NULL DEFAULT now(),
  ultimo_acceso  timestamptz
);

COMMENT ON COLUMN core.usuario.clave_hash IS
  'scrypt$n$r$p$salt_hex$hash_hex -- autodescriptivo, ver auth.py';
COMMENT ON COLUMN core.usuario.rol IS
  'ADMIN administra usuarios; AUDITOR usa la aplicación.';
COMMENT ON COLUMN core.usuario.activo IS
  'Se desactiva en vez de borrar: los papeles de trabajo referencian al usuario por nombre.';

CREATE TABLE core.sesion (
  token_hash  text PRIMARY KEY,
  usuario_id  uuid NOT NULL REFERENCES core.usuario(id) ON DELETE CASCADE,
  creada_en   timestamptz NOT NULL DEFAULT now(),
  expira_en   timestamptz NOT NULL,
  agente      text
);

COMMENT ON TABLE core.sesion IS
  'Sesiones activas. Se guarda sha256 del token, nunca el token mismo.';

CREATE INDEX ix_sesion_usuario ON core.sesion (usuario_id);
CREATE INDEX ix_sesion_expira  ON core.sesion (expira_en);

COMMIT;


-- =====================================================================
-- VERIFICACIÓN
-- =====================================================================

SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema='core' AND table_name IN ('usuario','sesion')
ORDER BY table_name, ordinal_position;
