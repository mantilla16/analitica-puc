-- =====================================================================
-- REPOSITORIO DE ANÁLISIS DE IA
--
-- Cada observación que redacta la IA queda guardada, anclada al cliente.
-- Al volver a abrir Variaciones no se regenera lo que ya existe: se
-- pinta lo guardado. El auditor puede pedirle un ajuste con sus propias
-- indicaciones y eso crea una VERSIÓN NUEVA sin borrar la anterior --
-- mismo criterio append-only de core.materialidad_historia.
--
-- Se guarda también `entrada`: el JSON exacto de agregados que recibió
-- el modelo. Es la evidencia de sobre qué cifras redactó, y es lo que
-- se vuelve a enviar cuando el auditor pide un ajuste.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 10_observacion_ia.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE core.observacion_ia (
  id                    bigserial PRIMARY KEY,
  cliente_id            uuid NOT NULL REFERENCES core.cliente(id) ON DELETE CASCADE,
  encargo_id            uuid REFERENCES core.encargo(id) ON DELETE SET NULL,
  fase                  text NOT NULL REFERENCES core.fase(fase),
  codigo_puc            text NOT NULL,
  version               integer NOT NULL,
  texto                 text NOT NULL,
  verificado            boolean NOT NULL DEFAULT false,
  cifras_no_verificadas jsonb,
  entrada               jsonb NOT NULL,
  instruccion_auditor   text,
  modelo                text,
  creado_por            text,
  creado_en             timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE core.observacion_ia IS
  'Append-only. La vigente es la fila de mayor version por (encargo_id, fase, codigo_puc).';
COMMENT ON COLUMN core.observacion_ia.cliente_id IS
  'El repositorio es del cliente: borrar un encargo no borra su historia de análisis.';
COMMENT ON COLUMN core.observacion_ia.entrada IS
  'Agregados que recibió el modelo. Evidencia de sobre qué cifras redactó.';
COMMENT ON COLUMN core.observacion_ia.instruccion_auditor IS
  'NULL en la primera versión. Con valor cuando el auditor pidió un ajuste.';
COMMENT ON COLUMN core.observacion_ia.modelo IS
  'Proveedor y modelo que redactó, ej. azure_foundry:DeepSeek-V4-Pro.';

CREATE INDEX ix_obs_ia_vigente
  ON core.observacion_ia (encargo_id, fase, codigo_puc, version DESC);

CREATE INDEX ix_obs_ia_cliente
  ON core.observacion_ia (cliente_id, creado_en DESC);

COMMIT;


-- =====================================================================
-- VERIFICACIÓN
-- =====================================================================

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema='core' AND table_name='observacion_ia'
ORDER BY ordinal_position;
