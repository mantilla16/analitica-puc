-- =====================================================================
-- CUENTAS EXCLUIDAS DEL ANALISIS POR DECISION DEL AUDITOR
--
-- El auditor puede decidir que una cuenta (o un grupo, o una clase
-- entera, p.ej. las cuentas de orden) no entra al analisis de
-- variaciones de un encargo. Es una decision de juicio profesional, y
-- como tal tiene que quedar documentada: un papel que omite cuentas sin
-- decir cuales ni por que no se puede firmar (NIA 230).
--
-- Por eso:
--   · `motivo` es obligatorio (la longitud minima se valida en Python).
--   · Queda quien y cuando.
--   · Se excluye por PREFIJO (1 a 4 digitos): '9' saca toda la clase 9,
--     '2408' saca solo esa cuenta. El analisis trabaja a nivel cuenta
--     (4 digitos), asi que no hay exclusiones parciales de una cuenta.
--
-- La exclusion no borra nada del balance: la cuenta sigue cargada y
-- visible en la pestaña Balance. Solo sale de la seleccion y del
-- residuo, y el papel la declara aparte con su motivo.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 24_cuentas_excluidas.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS core.cuenta_excluida (
    encargo_id   uuid        NOT NULL REFERENCES core.encargo(id) ON DELETE CASCADE,
    prefijo      text        NOT NULL,
    motivo       text        NOT NULL,
    excluido_por text,
    excluido_en  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (encargo_id, prefijo)
);

COMMENT ON TABLE core.cuenta_excluida IS
  'Cuentas que el auditor saco del analisis de variaciones de un encargo, '
  'con su motivo. No afecta el balance cargado; el papel las declara.';

COMMIT;
