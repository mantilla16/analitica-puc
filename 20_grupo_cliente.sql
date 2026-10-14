-- =====================================================================
-- GRUPO DE CLIENTES
--
-- Un auditor con 20+ clientes del grupo DAABON (sociedades distintas
-- pero mismo controlador) necesita filtrar la lista por grupo cuando
-- esta trabajando con ellos, en vez de recorrer una tabla de 50
-- razones sociales mezcladas. El grupo tambien aparece despues en
-- cedulas comparativas entre sociedades del mismo controlador.
--
-- Vive en core.cliente, no en core.encargo: el grupo lo determina el
-- controlador, no el encargo. Si una sociedad cambia de grupo (venta,
-- fusion), es un cambio del cliente que se refleja en todos sus
-- encargos.
--
-- Un indice funcional en lower(grupo) permite agrupar sin importar la
-- caja: 'DAABON', 'Daabon', 'daabon' son el mismo grupo.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 20_grupo_cliente.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE core.cliente
  ADD COLUMN IF NOT EXISTS grupo text;

COMMENT ON COLUMN core.cliente.grupo IS
  'Agrupador del cliente (controlador, holding, familia economica). '
  'Permite filtrar la lista de encargos cuando un mismo grupo tiene '
  'muchas sociedades.';

CREATE INDEX IF NOT EXISTS ix_cliente_grupo
  ON core.cliente (lower(grupo))
  WHERE grupo IS NOT NULL;

COMMIT;
