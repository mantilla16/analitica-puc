-- =====================================================================
-- BALANCES QUE SOLO TRAEN EL SALDO FINAL
--
-- Hay flujos donde el balance que llega a este motor YA venia validado
-- por un proceso previo del cliente: la integridad (saldo_inicial +
-- debito - credito = saldo_final a nivel linea, cuadre de clases a
-- cero) ya se verifico en origen y lo que entra son cifras consolidadas
-- al corte. Pedirle entonces las cuatro columnas obliga a mapear
-- columnas inventadas o a dejar vacias las que no vinieron, y abre una
-- puerta mas al error de mapeo que a la seguridad.
--
-- Con esta migracion, para BALANCE el unico requerido es:
--
--   · codigo_puc      -- sin codigo no hay cuenta a la que atribuir el saldo
--   · saldo_final     -- es el dato que entra al comparativo
--
-- Lo demas (saldo_inicial, debito, credito) queda opcional:
--
--   · Si vienen, se usan para cuadre por linea y para derivar el
--     comparativo del cierre anterior desde el arrastre. Mejor papel.
--   · Si no vienen, el motor avisa en el papel que el cuadre por
--     linea no se ejecuto -- no se calla el control, se declara que
--     no corrio -- y los comparativos van exigidos como insumos
--     aparte.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 18_balance_solo_saldo_final.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

UPDATE core.campo_canonico
   SET requerido = false
 WHERE naturaleza = 'BALANCE'
   AND campo IN ('debito', 'credito');
-- saldo_inicial ya estaba en requerido=false

COMMIT;
