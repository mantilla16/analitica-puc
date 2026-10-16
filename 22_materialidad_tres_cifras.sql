-- =====================================================================
-- MATERIALIDAD: TRES CIFRAS POR FASE
--
-- Hasta aqui cada fase tenia UNA cifra (`valor`) y el motor la usaba
-- directo como umbral de seleccion. Eso equivale a una materialidad de
-- desempeno del 100% de la global: no deja margen para errores no
-- detectados que se acumulan por debajo del umbral, y ninguna practica
-- de auditoria la admite.
--
-- Desde esta migracion cada fase lleva tres cifras:
--
--   · global     -- la columna `valor` existente. No se renombra: la
--                   leen demasiados puntos (papel, excel, frontend) y un
--                   rename romperia todos a la vez por una cuestion de
--                   nombre. Se documenta con COMMENT.
--   · desempeno  -- la que define el alcance (umbral de "Monto").
--   · trivial    -- el piso por debajo del cual una diferencia no se mira.
--
-- Desempeno y trivial se digitan como % de la global (modo PCT) o como
-- valor en pesos (modo VALOR); la otra forma se deriva en Python. Se
-- guardan las dos (pct y valor) para que el historial muestre lo que se
-- veia en pantalla aunque cambie la global despues.
--
-- Los rangos (desempeno 20-90%, trivial 2-10%) NO van como CHECK aqui:
-- regla del proyecto, la base guarda datos y la logica vive en reglas.py.
-- El CHECK del modo si va: es el dominio del dato, como el rol en 21.
--
-- Siembra de filas existentes: desempeno 75% (lo usual) y trivial con el
-- pct_trivialidad que ya tenia el encargo (5 si no tenia). Esa columna del
-- encargo se conserva pero el motor deja de leerla: el trivial ahora es
-- por fase.
--
-- Ademas se corrige el nombre por defecto de la fase de ejecucion: decia
-- "Materialidad de desempeno", que ahora es el nombre de una de las tres
-- cifras y confundia. Solo se renombra si coincide exacto con el default
-- viejo: si el auditor ya lo cambio, se respeta.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 22_materialidad_tres_cifras.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE core.materialidad
  ADD COLUMN IF NOT EXISTS desempeno_modo  text NOT NULL DEFAULT 'PCT'
      CHECK (desempeno_modo IN ('PCT','VALOR')),
  ADD COLUMN IF NOT EXISTS desempeno_pct   numeric(5,2),
  ADD COLUMN IF NOT EXISTS desempeno_valor numeric(19,2),
  ADD COLUMN IF NOT EXISTS trivial_modo    text NOT NULL DEFAULT 'PCT'
      CHECK (trivial_modo IN ('PCT','VALOR')),
  ADD COLUMN IF NOT EXISTS trivial_pct     numeric(5,2),
  ADD COLUMN IF NOT EXISTS trivial_valor   numeric(19,2);

ALTER TABLE core.materialidad_historia
  ADD COLUMN IF NOT EXISTS desempeno_modo  text NOT NULL DEFAULT 'PCT'
      CHECK (desempeno_modo IN ('PCT','VALOR')),
  ADD COLUMN IF NOT EXISTS desempeno_pct   numeric(5,2),
  ADD COLUMN IF NOT EXISTS desempeno_valor numeric(19,2),
  ADD COLUMN IF NOT EXISTS trivial_modo    text NOT NULL DEFAULT 'PCT'
      CHECK (trivial_modo IN ('PCT','VALOR')),
  ADD COLUMN IF NOT EXISTS trivial_pct     numeric(5,2),
  ADD COLUMN IF NOT EXISTS trivial_valor   numeric(19,2);

COMMENT ON COLUMN core.materialidad.valor IS
  'Materialidad GLOBAL de la fase, en pesos. La digita el auditor. '
  'No es el umbral de seleccion: ese es desempeno_valor.';
COMMENT ON COLUMN core.materialidad.desempeno_valor IS
  'Materialidad de desempeno en pesos: umbral de seleccion por Monto. '
  'Derivada de desempeno_pct cuando desempeno_modo = PCT.';
COMMENT ON COLUMN core.materialidad.trivial_valor IS
  'Error trivial en pesos de la fase. Derivado de trivial_pct cuando '
  'trivial_modo = PCT.';
COMMENT ON COLUMN core.encargo.pct_trivialidad IS
  'OBSOLETA desde 22_materialidad_tres_cifras: el trivial es por fase '
  '(core.materialidad.trivial_*). Se conserva solo como historia.';

-- Siembra. Idempotente: solo toca filas que aun no tienen porcentaje, asi
-- que correrla dos veces no pisa lo que el auditor haya digitado despues.
UPDATE core.materialidad m
   SET desempeno_modo  = 'PCT',
       desempeno_pct   = 75,
       desempeno_valor = CASE WHEN m.valor IS NOT NULL
                              THEN round(m.valor * 75 / 100, 2) END,
       trivial_modo    = 'PCT',
       trivial_pct     = coalesce(e.pct_trivialidad, 5),
       trivial_valor   = CASE WHEN m.valor IS NOT NULL
                              THEN round(m.valor * coalesce(e.pct_trivialidad, 5) / 100, 2) END
  FROM core.encargo e
 WHERE e.id = m.encargo_id
   AND m.desempeno_pct IS NULL
   AND m.trivial_pct IS NULL;

-- Nombres por defecto. Planeacion y cierre ya tienen el nombre nuevo.
UPDATE core.materialidad
   SET nombre = 'Materialidad de ejecución'
 WHERE fase = 'EJECUCION'
   AND nombre = 'Materialidad de desempeño';

COMMIT;
