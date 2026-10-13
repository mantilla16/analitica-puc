-- =====================================================================
-- BALANCES QUE SOLO TRAEN AUXILIARES
--
-- Hasta aqui el motor asumia el formato clasico de Helisa, World Office,
-- Siigo: el archivo ya viene "plegado", trayendo una fila por cada
-- nivel (Clase, Cuenta, Subcuenta, Auxiliar). Los ERPs tipo SAP no
-- funcionan asi: exportan solo las hojas del arbol -- cuentas de 10
-- digitos -- y asumen que los agrupadores los calcula quien pinte el
-- reporte.
--
-- El grupo DAABON tiene 20+ sociedades y todas vienen de SAP: un
-- balance tipico trae 248 filas de 10 digitos y cero de niveles
-- superiores. Hasta aqui el motor excluia esas 248 filas (porque
-- Subauxiliar no era cargable), no encontraba padre contenedor y
-- bloqueaba la carga con SALDO_EXCLUIDO_PERDIDO. Correcto desde la
-- regla, inutil desde el papel: no hay papel que armar.
--
-- Dos cambios aqui, que juntos cierran la pinza:
--
--   1. Subauxiliar (10 digitos) se hace nivel cargable. Las hojas que
--      exporte SAP si entran al balance.
--
--   2. core.balance gana una columna `origen`: 'ARCHIVO' para lo que
--      vino tal cual, 'SINTETIZADO' para los agrupadores que el motor
--      deriva sumando las hojas. El papel tiene que poder declararlo:
--      es la diferencia entre "lo revise todo del archivo" y "parte lo
--      calcule yo porque el archivo no lo traia".
--
-- Para los clientes que SI traen los niveles completos (Helisa & cia)
-- nada cambia: `origen` entra con default 'ARCHIVO' y el motor no
-- sintetiza lo que ya esta. Para DAABON, el gate G01 cuadra porque los
-- Clase/Cuenta/Subcuenta sintetizados reproducen la ecuacion contable.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 16_balances_de_sap.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

-- ------------------------------------------------------------------ 1
-- Subauxiliar entra como nivel cargable. nivel_completo=false porque
-- no todas las ramas del arbol bajan a 10 digitos: cuadrar en ese
-- nivel seria pedirle al archivo que incluya cosas que no existen.
INSERT INTO core.nivel_cargable
       (nivel, digitos, es_comparativo, nivel_completo, orden, nota)
VALUES ('Subauxiliar', 10, false, false, 5,
        'Hoja del arbol. No cuadra solo. ERPs tipo SAP solo exportan este nivel.')
ON CONFLICT (nivel) DO NOTHING;

-- ------------------------------------------------------------------ 2
-- Procedencia de la fila. Lo cargado de archivos previos queda como
-- 'ARCHIVO': es correcto -- en ese momento no habia sintesis.
ALTER TABLE core.balance
  ADD COLUMN IF NOT EXISTS origen text NOT NULL DEFAULT 'ARCHIVO';

ALTER TABLE core.balance
  DROP CONSTRAINT IF EXISTS balance_origen_chk;
ALTER TABLE core.balance
  ADD CONSTRAINT balance_origen_chk
    CHECK (origen IN ('ARCHIVO','SINTETIZADO'));

COMMENT ON COLUMN core.balance.origen IS
  'ARCHIVO: la fila vino tal cual en la carga. SINTETIZADO: el motor '
  'la derivo sumando sus hijos, porque el archivo solo trajo niveles '
  'mas finos (tipico de exports de SAP). El papel la declara aparte: '
  'no es lo mismo haber revisado todo que haber calculado parte.';

COMMIT;
