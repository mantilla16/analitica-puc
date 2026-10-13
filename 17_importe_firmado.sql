-- =====================================================================
-- MOVIMIENTOS CON UN SOLO IMPORTE FIRMADO
--
-- Los auxiliares clasicos (Helisa, World Office, Siigo) traen dos
-- columnas separadas: debito y credito, cada movimiento usa una. SAP
-- en cambio exporta UNA columna "Importe en ML" con signo: positivo
-- es un debito registrado, negativo es un credito. Es la convencion
-- de SAP y la de varios ERPs mas modernos. El grupo DAABON (20+
-- sociedades) usa este formato en todos sus auxiliares.
--
-- Hasta aqui el motor rechazaba el mapeo porque faltaban las dos
-- columnas. Ahora:
--
--   · Se acepta como requerido alternativo un campo `importe_firmado`.
--   · debito y credito dejan de ser requeridos: basta con que venga
--     uno de los dos caminos (ambas columnas, o la unica con signo).
--   · El motor divide `importe_firmado` en debito/credito segun el
--     signo antes de guardar en staging. Lo que viva aguas abajo no
--     se entera: cuadres, hallazgos y papeles leen debito/credito
--     exactamente igual.
--
-- La validacion de "al menos uno" se hace en reglas.validar_mapeo:
-- aqui solo se marcan los tres como no requeridos para que el chequeo
-- actual (campo_requerido_sin_mapear) no bloquee. El reemplazo del
-- requerido singular por "uno de estos dos conjuntos" es logica, no
-- declarativa, y vive mejor en el codigo.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 17_importe_firmado.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

-- ------------------------------------------------------------------ 1
-- debito y credito dejan de ser requeridos: la nueva validacion exige
-- uno de los dos caminos. Dejarlos requeridos ademas haria imposible
-- cargar un archivo que trae el importe firmado.
UPDATE core.campo_canonico
   SET requerido = false
 WHERE naturaleza = 'MOVIMIENTO' AND campo IN ('debito', 'credito');

-- ------------------------------------------------------------------ 2
-- El nuevo campo. Requerido=false aqui mismo: la obligacion es "uno de
-- los dos conjuntos", y eso solo la aplica la validacion de reglas.py.
INSERT INTO core.campo_canonico
       (naturaleza, campo, etiqueta, tipo, requerido, es_llave, orden, ayuda)
VALUES ('MOVIMIENTO', 'importe_firmado', 'Importe con signo', 'numero',
        false, false, 13,
        'Columna unica con signo: positivo es debito registrado, negativo '
        'es credito. SAP la exporta como "Importe en ML". Si viene esta, '
        'no hace falta llenar debito/credito; el motor las deriva del signo.')
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------------ 3
-- Sinonimos frecuentes del encabezado en los exportes reales. Ya hay
-- un sugeridor automatico pero estos aceleran el reconocimiento la
-- primera vez.
INSERT INTO core.campo_sinonimo (naturaleza, campo, sinonimo, norm) VALUES
  ('MOVIMIENTO', 'importe_firmado', 'Importe en ML',       'importe en ml'),
  ('MOVIMIENTO', 'importe_firmado', 'Importe en MC',       'importe en mc'),
  ('MOVIMIENTO', 'importe_firmado', 'Importe',             'importe'),
  ('MOVIMIENTO', 'importe_firmado', 'Importe ML',          'importe ml'),
  ('MOVIMIENTO', 'importe_firmado', 'Importe MC',          'importe mc'),
  ('MOVIMIENTO', 'importe_firmado', 'Valor en ML',         'valor en ml'),
  ('MOVIMIENTO', 'importe_firmado', 'Valor',               'valor'),
  ('MOVIMIENTO', 'importe_firmado', 'Monto',               'monto')
ON CONFLICT DO NOTHING;

COMMIT;
