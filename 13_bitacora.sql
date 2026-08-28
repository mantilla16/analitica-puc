-- =====================================================================
-- BITÁCORA DE USO
--
-- Quién hizo qué, cuándo y desde dónde. Una herramienta de auditoría
-- tiene que poder auditarse a sí misma: si alguien pregunta quién
-- reemplazó el balance el 12 de agosto o quién bajó la materialidad
-- antes del cierre, la respuesta no puede depender de la memoria.
--
-- Se registra TODO lo que modifica datos, más los ingresos (incluidos
-- los fallidos, que son la señal de que alguien está tanteando).
-- Las consultas de lectura no se registran: serían ruido y no cambian
-- nada.
--
-- `usuario` va desnormalizado a propósito: el registro debe seguir
-- siendo legible aunque la cuenta se desactive o se renombre.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 13_bitacora.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE core.bitacora (
  id          bigserial PRIMARY KEY,
  usuario_id  uuid REFERENCES core.usuario(id) ON DELETE SET NULL,
  usuario     text,
  accion      text NOT NULL,
  entidad     text,
  entidad_id  text,
  encargo_id  uuid REFERENCES core.encargo(id) ON DELETE SET NULL,
  detalle     jsonb,
  exito       boolean NOT NULL DEFAULT true,
  estado_http smallint,
  ip          text,
  agente      text,
  creado_en   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE core.bitacora IS
  'Rastro de uso. Solo escrituras e ingresos; las lecturas no se registran.';
COMMENT ON COLUMN core.bitacora.usuario IS
  'Desnormalizado: el registro sigue siendo legible aunque la cuenta cambie.';
COMMENT ON COLUMN core.bitacora.detalle IS
  'Contexto de la acción: nombre del archivo, valores guardados, cuenta afectada.';
COMMENT ON COLUMN core.bitacora.exito IS
  'false en ingresos fallidos y en peticiones que terminaron en error.';
COMMENT ON COLUMN core.bitacora.ip IS
  'Tomada de X-Real-IP / X-Forwarded-For: detrás de nginx, la dirección
   directa siempre sería 127.0.0.1.';

CREATE INDEX ix_bitacora_fecha   ON core.bitacora (creado_en DESC);
CREATE INDEX ix_bitacora_usuario ON core.bitacora (usuario_id, creado_en DESC);
CREATE INDEX ix_bitacora_encargo ON core.bitacora (encargo_id, creado_en DESC);
CREATE INDEX ix_bitacora_accion  ON core.bitacora (accion, creado_en DESC);

COMMIT;


-- =====================================================================
-- VERIFICACIÓN
-- =====================================================================

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema='core' AND table_name='bitacora'
ORDER BY ordinal_position;
