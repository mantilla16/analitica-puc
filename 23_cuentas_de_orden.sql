-- =====================================================================
-- CUENTAS DE ORDEN (CLASES 8 Y 9)
--
-- Hasta aqui el motor solo aceptaba codigos que empezaran por 1-7 y
-- dejaba fuera las cuentas de orden como si fueran titulos. En Terminal
-- de Graneles (DAABON) eso excluia 9115150001 y 9415150002 (bienes
-- recibidos de terceros, +-5.467 millones) y 9999999910: informacion que
-- el auditor si quiere ver.
--
-- Se agregan al catalogo de clases para que el balance, el drill, las
-- variaciones y el papel las muestren:
--
--   8  Cuentas de orden deudoras    naturaleza D
--   9  Cuentas de orden acreedoras  naturaleza C
--
-- Comparativo: CIERRE_ANTERIOR, igual que activo y pasivo. Son saldos
-- (derechos y obligaciones contingentes, bienes de terceros), no flujos
-- del periodo.
--
-- NO entran a la ecuacion contable: el cuadre a cero sigue siendo sobre
-- las clases 1 a 7 (reglas.CLASES_ECUACION). Las cuentas de orden se
-- cuadran entre si con su "por contra" y no siempre se llevan completas;
-- sumarlas convertiria una contrapartida mal llevada en un descuadre del
-- balance entero.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 23_cuentas_de_orden.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

INSERT INTO core.puc_clase (clase, nombre, naturaleza, signo, tipo_estado, comparativo)
SELECT v.* FROM (VALUES
    ('8', 'Cuentas de orden deudoras',   'D',  1, 'ORDEN', 'CIERRE_ANTERIOR'),
    ('9', 'Cuentas de orden acreedoras', 'C', -1, 'ORDEN', 'CIERRE_ANTERIOR')
) AS v(clase, nombre, naturaleza, signo, tipo_estado, comparativo)
WHERE NOT EXISTS (SELECT 1 FROM core.puc_clase p WHERE p.clase = v.clase);

COMMIT;
