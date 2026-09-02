-- =====================================================================
-- CONVENCIÓN DE SIGNO Y NIVELES QUE FALTABAN
--
-- Dos hallazgos del encargo de FGC, y los dos venían de suponer que todos
-- los clientes exportan igual.
--
-- 1. LA CONVENCIÓN DE SIGNO NO ES UNIVERSAL.
--
-- LIQUITECH entrega los pasivos en positivo y el sistema les aplica el
-- signo del catálogo para poder sumarlos. FGC los entrega YA con signo:
-- pasivos, patrimonio e ingresos vienen negativos, y sus cinco clases
-- suman exactamente cero tal como están.
--
-- Aplicarles el signo del catálogo los invierte por segunda vez, y el
-- balance descuadra por el doble del pasivo más el patrimonio -- 28.607
-- millones en el corte de mayo. El papel salía NO CONCLUYENTE por una
-- suposición del sistema, no por un problema del cliente.
--
-- La convención se DETECTA probando cuál de las dos hipótesis hace cuadrar
-- las clases en cero, y queda registrada en la carga. No se configura a
-- mano: un parámetro que alguien puede poner mal es una forma de descuadre
-- esperando ocurrir, y aquí hay una prueba objetiva disponible.
--
-- `saldo_natural` pasa a ser la cifra COMPARABLE (la que suma cero) y
-- `saldo_naturaleza` la que dice de qué lado está el saldo frente a su
-- naturaleza. Con la convención de LIQUITECH las dos coinciden; con la de
-- FGC difieren en signo para las clases 2, 3 y 4. Separarlas es lo que
-- evita que el criterio de "naturaleza invertida" marque todos los pasivos
-- de FGC como excepción.
--
-- 2. FALTABAN NIVELES.
--
-- El catálogo tenía 1, 4, 6 y 8 dígitos. FGC usa 1, 2, 4, 6 y 9: se
-- descartaban los 22 grupos y los 253 auxiliares, más de la mitad del
-- archivo. Los niveles nuevos no afectan a quien no los use -- si un
-- cliente no trae códigos de 2 dígitos, ese nivel simplemente no aparece.
--
-- Ninguno de los dos nuevos se declara `nivel_completo`: comprobé contra
-- el archivo real que no cuadran por sí solos, y declarar completo un
-- nivel que no cuadra haría fallar G01 en falso.
--
--   psql "$AUDITORIA_DSN" -v ON_ERROR_STOP=1 -f 14_convencion_signo.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

-- ------------------------------------------------- convención en la carga
ALTER TABLE core.carga
  ADD COLUMN IF NOT EXISTS convencion_signo text;

COMMENT ON COLUMN core.carga.convencion_signo IS
  'CATALOGO: el archivo trae los saldos en positivo y el signo se toma de '
  'core.puc_clase. ARCHIVO: el archivo ya trae los saldos con signo y se '
  'usan tal cual. INDETERMINADA: ninguna de las dos hace cuadrar las clases '
  'en cero, y se declara en vez de suponer una.';

-- ------------------------------------------ la cifra frente a su naturaleza
ALTER TABLE core.balance
  ADD COLUMN IF NOT EXISTS saldo_naturaleza numeric(19,2);

COMMENT ON COLUMN core.balance.saldo_natural IS
  'La cifra COMPARABLE: la que suma cero en un nivel completo y con la que '
  'se calculan las variaciones.';
COMMENT ON COLUMN core.balance.saldo_naturaleza IS
  'saldo_final por el signo del CATÁLOGO. Negativa cuando la cuenta está '
  'del lado contrario al de su naturaleza. Solo sirve para ese criterio; '
  'no se suma.';

-- Para lo ya cargado, las dos cifras coinciden: se promovió con la
-- convención del catálogo, que era la única que existía.
UPDATE core.balance
   SET saldo_naturaleza = saldo_natural
 WHERE saldo_naturaleza IS NULL;

UPDATE core.carga
   SET convencion_signo = 'CATALOGO'
 WHERE naturaleza = 'BALANCE' AND convencion_signo IS NULL;

-- ------------------------------------------------------ niveles que faltaban
INSERT INTO core.nivel_cargable (nivel, digitos, es_comparativo,
                                 nivel_completo, orden, nota)
VALUES
  ('Grupo', 2, false, false, 2,
   'Dos dígitos. No todos los clientes lo exportan; comprobado que no '
   'cuadra por sí solo en los archivos reales, así que no se declara completo.'),
  ('Subauxiliar', 9, false, false, 6,
   'Nueve dígitos. Es el nivel más granular de algunos ERP -- en FGC es su '
   'auxiliar. Drill-down: no cuadra solo.')
ON CONFLICT DO NOTHING;

-- Orden de lectura del balance, de lo más agregado a lo más detallado.
UPDATE core.nivel_cargable SET orden = 1 WHERE nivel = 'Clase';
UPDATE core.nivel_cargable SET orden = 2 WHERE nivel = 'Grupo';
UPDATE core.nivel_cargable SET orden = 3 WHERE nivel = 'Cuenta';
UPDATE core.nivel_cargable SET orden = 4 WHERE nivel = 'Subcuenta';
UPDATE core.nivel_cargable SET orden = 5 WHERE nivel = 'Auxiliar';
UPDATE core.nivel_cargable SET orden = 6 WHERE nivel = 'Subauxiliar';

COMMIT;


-- =====================================================================
-- VERIFICACIÓN
-- =====================================================================

SELECT nivel, digitos, es_comparativo, nivel_completo, orden
  FROM core.nivel_cargable ORDER BY orden;
