-- =====================================================================
-- SECUENCIA DE MOVIMIENTO: OPCIONAL
--
-- Varios ERPs no exportan una columna de secuencia dentro del
-- comprobante. SAP es el caso tipico: en el "Reporte JE" cada fila
-- es su propio movimiento, identificado por (num_doc, codigo_puc) y
-- el orden en la hoja. No hay un numero de renglon que se pueda
-- mapear.
--
-- Pedirla como obligatoria obligaba a mapearla a cualquier columna
-- "parecida" (p.ej. 'Asignacion', que no es renglon ni es unica).
-- Resultado: el COPY cargaba filas con secuencias equivocadas y la
-- llave natural dejaba de distinguir movimientos distintos.
--
-- Ahora:
--   · secuencia deja de ser requerida.
--   · Si viene mapeada, se usa tal cual.
--   · Si no viene, el motor la sintetiza desde fila_origen (es decir,
--     el numero de fila en el Excel), que es unico por archivo. La
--     logica de ese fallback vive en excel.parsear.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 19_secuencia_opcional.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

UPDATE core.campo_canonico
   SET requerido = false
 WHERE naturaleza = 'MOVIMIENTO' AND campo = 'secuencia';

COMMIT;
