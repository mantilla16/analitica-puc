-- =====================================================================
-- CRITERIOS DE SELECCIÓN OPCIONALES
--
-- Hasta ahora el porcentaje de variación y el error trivial siempre
-- aplicaban. El auditor necesita poder apagarlos según el encargo:
--
--   · Sin error trivial, el criterio de porcentaje queda "absoluto":
--     cualquier cuenta que varíe más del X% se reporta, sin importar
--     cuán pequeña sea la cifra.
--   · Sin criterio de porcentaje, la selección se apoya solo en la
--     materialidad en pesos y en los criterios estructurales (cuenta
--     nueva, cerrada, naturaleza).
--
-- Son banderas y no valores nulos para que apagar un criterio no borre
-- el porcentaje configurado: se puede volver a encender sin re-teclearlo.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 12_criterios_opcionales.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE core.encargo
  ADD COLUMN aplica_variacion   boolean NOT NULL DEFAULT true,
  ADD COLUMN aplica_trivialidad boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN core.encargo.aplica_variacion IS
  'Si el criterio de porcentaje (Comportamiento) participa en la selección.';
COMMENT ON COLUMN core.encargo.aplica_trivialidad IS
  'Si el error trivial filtra los criterios distintos de Monto.';

COMMIT;


-- =====================================================================
-- VERIFICACIÓN
-- =====================================================================

SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_schema='core' AND table_name='encargo'
  AND column_name IN ('pct_variacion','pct_trivialidad',
                      'aplica_variacion','aplica_trivialidad')
ORDER BY column_name;
