-- =====================================================================
-- MATERIALIDAD POR FASE
--
-- El ejercicio se hace en tres fases: planeación, ejecución y cierre.
-- Cada una tiene su propia materialidad, digitada por el auditor, y él
-- decide cuáles aplicar.
--
-- Reemplaza el modelo anterior de una materialidad con factores derivados.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 08_materialidad.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

-- Catálogo de fases. Tabla, no CHECK: agregar una fase es un INSERT.
CREATE TABLE core.fase (
  fase   text PRIMARY KEY,
  nombre text NOT NULL,
  orden  smallint NOT NULL
);

INSERT INTO core.fase VALUES
  ('PLANEACION', 'Planeación', 1),
  ('EJECUCION',  'Ejecución',  2),
  ('CIERRE',     'Cierre',     3);


-- Parámetros de selección, comunes a todas las fases.
ALTER TABLE core.encargo
  ADD COLUMN fase_activa      text REFERENCES core.fase(fase) DEFAULT 'PLANEACION',
  ADD COLUMN pct_variacion    numeric(5,2) NOT NULL DEFAULT 20.00,
  ADD COLUMN pct_trivialidad  numeric(5,2) NOT NULL DEFAULT 5.00;

COMMENT ON COLUMN core.encargo.pct_variacion IS
  'Variación porcentual que marca una cuenta aunque no supere el umbral en pesos';
COMMENT ON COLUMN core.encargo.pct_trivialidad IS
  'Piso de ruido, como porcentaje de la materialidad de la fase activa';


-- Materialidad: una fila por fase. El valor lo digita el auditor.
DROP TABLE IF EXISTS core.materialidad;

CREATE TABLE core.materialidad (
  id            bigserial PRIMARY KEY,
  encargo_id    uuid NOT NULL REFERENCES core.encargo(id) ON DELETE CASCADE,
  fase          text NOT NULL REFERENCES core.fase(fase),
  nombre        text NOT NULL,
  valor         numeric(19,2),
  porcentaje    numeric(5,2),      -- referencia respecto a la de planeación
  aplicar       boolean NOT NULL DEFAULT false,
  base_calculo  text,
  aprobado_por  text,
  actualizado   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (encargo_id, fase)
);

CREATE INDEX ix_materialidad ON core.materialidad (encargo_id, fase);


-- Historial: cada cambio de valor queda registrado.
CREATE TABLE core.materialidad_historia (
  id            bigserial PRIMARY KEY,
  encargo_id    uuid NOT NULL REFERENCES core.encargo(id) ON DELETE CASCADE,
  fase          text NOT NULL,
  nombre        text NOT NULL,
  valor         numeric(19,2),
  porcentaje    numeric(5,2),
  aplicar       boolean NOT NULL,
  cambiado_por  text,
  cambiado_en   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_mat_historia ON core.materialidad_historia (encargo_id, cambiado_en DESC);

COMMIT;


-- =====================================================================
-- VERIFICACIÓN
-- =====================================================================

SELECT fase, nombre, orden FROM core.fase ORDER BY orden;

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema='core' AND table_name='materialidad'
ORDER BY ordinal_position;
