# Esquema de la base de datos

Postgres 18, base `auditoria_puc`. **Decisión de diseño explícita: la base
tiene solo tablas, llaves foráneas e índices.** Cero funciones, vistas,
triggers o columnas generadas. Toda la lógica de negocio (fechas, signo por
herencia, cuadres, cotejo, materialidad) vive en `reglas.py` y se prueba sin
levantar la base.

Este documento explica **qué es y para qué sirve cada tabla**. La
definición exacta (tipos, `NOT NULL`, índices) está en
[`schema.sql`](schema.sql), que es la fuente de verdad — este archivo es la
guía de lectura.

Tres grupos de tablas por cómo se usan:

1. **Catálogo** -- semilla fija, no cambia por encargo.
2. **Operación** -- lo que crea el auditor (clientes, encargos, cargas, materialidad).
3. **Staging y datos** -- lo que entra de los Excel y lo ya validado.
4. **Evidencia** -- el rastro de cotejos, hallazgos y alertas.

---

## 1. Catálogo

Datos que se cargan una vez y no dependen de ningún cliente ni encargo.

### `core.puc_clase`
Las 7 clases del PUC (1 Activo … 7, aunque este proyecto no usa la 7).
Columnas: `clase` (PK, '1'..'7'), `nombre`, `naturaleza` ('D'/'C'),
`signo` (1 débito / -1 crédito), `tipo_estado` (`BALANCE` para 1-3,
`RESULTADO` para 4-7), y **`comparativo`** (`CIERRE_ANTERIOR` para 1-3,
`MISMO_PERIODO` para 4-7 -- la regla de qué se compara contra qué,
guardada como dato de la clase, tal como pide el diseño).

`signo_por_clase()` en `db.py` sí lee esta tabla para resolver la
naturaleza de cualquier código sin excepción declarada. **`comparativo`
está en el esquema pero `analisis.variaciones()` todavía no lo lee** --
hoy decide con un umbral fijo en Python (`if clase <= "3"`) que da el
mismo resultado, pero no consulta esta columna. Si algún día se necesita
una regla de comparativo distinta a la partición 1-3/4-7, hay que
cambiar el código para que lea de aquí, porque ahora mismo el dato y la
lógica están desincronizados por construcción.

### `core.puc_nivel`
Los 6 niveles jerárquicos del PUC y su longitud de código: Clase(1),
Grupo(2), Cuenta(4), Subcuenta(6), Auxiliar(8), Subauxiliar(10). Es la
tabla de referencia; `core.nivel_cargable` decide cuáles de estos 6
realmente se cargan.

### `core.nivel_cargable`
De los 6 niveles, cuáles se promueven a `core.balance`: Clase, Cuenta,
Subcuenta y Auxiliar (Grupo y Subauxiliar se descartan al promover, son
redundantes o incompletos). Columnas: `nivel`, `digitos`, `orden`,
`nivel_completo` (si ese nivel por sí solo debe sumar cero),
`es_comparativo` (marca **Cuenta** como el nivel al que se comparan las
variaciones). `promover_balance()` en `servicios.py` filtra por esta tabla
fila por fila.

### `core.puc`
Catálogo completo del Decreto 2650: 354 códigos con `codigo` (PK),
`nombre`, `clase`, `digitos`, `origen` (`decreto2650` para el catálogo
oficial, `derivado` para lo que se infiere), `validado` y `activo`
(banderas de mantenimiento del catálogo), y `naturaleza` (nullable --
**NULL significa "hereda de la clase o de un prefijo más corto"**). Solo
tiene valor en las 16 filas que
son excepción real: contra-activos (1299, 1399, 1499, 1592, 1597, 1598,
1599, 1698, 1699, 1798, 1899), resultados que se comportan al revés (3610,
3710), y las tres que el propio PUC marca `(DB)`/`(CR)` (4175, 4275,
6225). `resolver_signo()` en `reglas.py` recorre el código de más largo a
más corto buscando la excepción más específica; si no encuentra ninguna,
usa el signo de la clase. Así `159205` resuelve a crédito porque `1592`
está declarada, sin que nadie tenga que registrar `159205` aparte.

Los **nombres que ve el auditor no salen de aquí**: `core.balance` guarda
el nombre tal como vino en el Excel del cliente (que puede usar
terminología NIIF, no Decreto 2650). `core.puc` solo se usa como
respaldo (`nombres_puc()`) cuando una cuenta no aparece en la carga actual.

### `core.insumo`
Los 6 tipos de archivo que puede recibir un encargo: `BAL_ACTUAL`,
`BAL_CIERRE_ANTERIOR`, `BAL_CORTE_ANTERIOR`, `MOV_ACTUAL`, `MOV_ANTERIOR`,
`PRECOMPROBANTE`. Columnas: `tipo` (PK), `nombre`, `naturaleza`
(`BALANCE`/`MOVIMIENTO`, decide qué parser usa `excel.py`), `requerido`,
`orden`, y `rol_comparativo` (sin usar por el código todavía, mismo caso
que `puc_clase.comparativo`). El checklist de la pestaña Archivos es
literalmente un `LEFT JOIN` de esta tabla contra `core.encargo_insumo`.

### `core.campo_canonico` y `core.campo_sinonimo`
El corazón del perfil de mapeo. `campo_canonico` (20 filas: `naturaleza`,
`campo`, `etiqueta`, `tipo` de dato, `requerido`, `es_llave` -- marca los
campos que participan en la llave natural de cotejo --, `orden`, `ayuda`)
es **el estándar fijo** contra el que el auditor relaciona las columnas
de su Excel (`codigo_puc`, `saldo_inicial`, `debito`, `num_doc`,
`descripcion`, etc.). `campo_sinonimo` (65 filas: `naturaleza`, `campo`,
`sinonimo`, `norm` -- el sinónimo normalizado, para comparar sin
importar tildes/mayúsculas) son nombres de encabezado alternativos
("Código cuenta contable", "Cta contable", "Cuenta") que `excel.py` usa
para **sugerir** el mapeo automáticamente en la segunda carga de un mismo
cliente. Nunca se mapea por posición de columna -- siempre por nombre,
porque un mismo cliente puede mandar archivos con distinto número de
columnas entre periodos.

### `core.fase`
Las 3 fases del ejercicio de auditoría: `PLANEACION`, `EJECUCION`,
`CIERRE`, cada una con su `orden`. Cada `core.encargo` tiene una
`fase_activa` que apunta aquí, y cada fase tiene su propia fila en
`core.materialidad`.

---

## 2. Operación

Lo que se crea a medida que se trabaja un encargo.

### `core.cliente`
`id` (PK), `nit`, `razon_social`, `seudonimo`. El `seudonimo` existe para
que la capa de IA reciba agregados anonimizados en vez de la razón social
real -- hoy `ia.py` ni siquiera recibe el cliente, así que esta columna
está lista mirando hacia adelante, cuando la capa de IA analice más que
una cuenta suelta.

### `core.encargo`
Un ejercicio de auditoría para un cliente en un corte específico. Columnas
clave: `cliente_id` (FK), `fecha_corte`, `fecha_cierre_anterior` y
`fecha_corte_anterior` (las dos últimas las calcula `reglas.py`, no las
teclea el auditor), `estado`, `responsable`, y -- agregadas en la
migración de materialidad -- `fase_activa` (FK a `core.fase`),
`pct_variacion` y `pct_trivialidad` (los parámetros de selección,
comunes a las tres fases).

### `core.materialidad`
Una fila por `(encargo_id, fase)` -- `UNIQUE` compuesta. `valor` y
`porcentaje` los digita el auditor (el sistema nunca inventa un umbral);
`aplicar` decide si esa fase realmente se usa en Variaciones. Si
`aplica=false` o `valor` es `NULL`, `analisis.variaciones()` devuelve
todas las cuentas sin marcar ninguna, en vez de fabricar un umbral.

### `core.materialidad_historia`
**Append-only**: cada vez que se guarda un cambio en `core.materialidad`
(`guardar_materialidad()` en `db.py`), queda una fila nueva aquí con quién
lo cambió y cuándo. Nunca se hace `UPDATE` sobre el historial, solo
`INSERT` -- es el patrón que se repitió después para cualquier otra cosa
que necesite quedar versionada en vez de sobrescrita.

### `core.perfil_mapeo`
El mapeo de columnas confirmado por el auditor para un `(cliente_id,
tipo)`, versionado (`version`, `vigente`). El mapeo en sí (`mapeo`, jsonb)
guarda qué columna del Excel corresponde a cada campo canónico, la hoja a
usar, y el formato de fecha. Un cliente nuevo con un layout distinto es
una fila nueva aquí -- cero SQL, cero cambios de código.

### `core.carga`
Cada archivo subido, una fila. Columnas clave: `cliente_id`, `encargo_id`,
`tipo`, `archivo` (ruta en disco), `hash_sha256` (para detectar
`ARCHIVO_IDENTICO`), `periodo_ini`/`periodo_fin`, `perfil_id`, `estado`,
`filas_staging`, `filas_cargadas`.

**La carga pertenece al cliente, no al encargo** -- los movimientos de
2025 se cargan una vez y sirven como `MOV_ACTUAL` del encargo 2025 y
`MOV_ANTERIOR` del encargo 2026 (ver `core.encargo_insumo`).

`estado` recorre este ciclo:

| Estado | Cuándo |
|---|---|
| `CARGADA` | Se subió y quedó en staging, aún no se promovió (típico en movimientos, que no se promueven hoy). |
| `VALIDADA` | Se promovió a `core.balance` y el cuadre por línea y por nivel salió limpio. |
| `CON_HALLAZGOS` | Se promovió, pero `cuadre_por_linea`/`cuadre_por_nivel` encontraron algo -- la carga queda visible pero marcada, no se descarta en silencio. |
| `RECHAZADA` | Falló el procesamiento (excepción durante `S.procesar`). |
| `REEMPLAZADA` | Se detectó `ARCHIVO_IDENTICO` o `SIN_FILAS_NUEVAS` al recargar -- la carga vieja queda marcada así. |

### `core.encargo_insumo`
La tabla que resuelve "qué carga cumple qué rol en qué encargo":
`(encargo_id, tipo)` → `carga_id`, con `UNIQUE (encargo_id, tipo)` y
`ON CONFLICT DO UPDATE` -- subir un archivo nuevo para el mismo tipo
reasigna el puntero al instante, sin duplicar filas.

---

## 3. Staging y datos

### `raw.balance_staging` / `raw.movimiento_staging`
Todo lo que sale de `excel.parsear()`, **todavía en texto**, una fila por
renglón del Excel. Columnas propias de cotejo: `carga_id`, `llave` (huella
de identidad -- para balance es solo el código de cuenta; para movimiento
es `comprobante + secuencia + código`, verificada única en 122.795 filas
reales) y `huella` (hash de todos los valores, para detectar si una fila
con la misma llave cambió). `fila_origen` guarda el número de fila del
Excel para poder señalar el error exacto si algo no cuadra.

Es la base del cotejo de recargas: comparar `{llave: huella}` de la carga
nueva contra la anterior clasifica cada fila en nueva, modificada,
eliminada o sin cambios -- sin tocar Postgres más que para leer.

### `core.balance`
El balance ya **validado y tipado** -- lo que ve la pestaña Balance.
Columnas: `carga_id`, `cliente_id`, `codigo_puc`, `nombre_cuenta`,
`nivel`, `digitos`, `clase`, `cuenta` (prefijo de 4 dígitos, para agrupar
sin repetir el join), `subcuenta` (prefijo de 6), `saldo_inicial`,
`debito`, `credito`, `saldo_final`, `signo` (resuelto por herencia al
promover), `saldo_natural` (`saldo_final × signo` -- el valor que de
verdad se compara entre periodos, para que una cuenta de naturaleza
crédito que crece no se vea como que "bajó").

`promover_balance()` en `db.py` hace `DELETE ... WHERE carga_id=%s` antes
de insertar: cada promoción reemplaza limpio, no acumula. Los niveles no
se suman entre sí -- cada uno es el balance completo, solo más
desglosado; se lee el que haga falta, nunca se combinan.

### `core.movimiento`
**Existe en el esquema, con todas sus columnas, pero todavía no se
promueve nada aquí.** `PARTITION BY RANGE (fecha)`, con particiones ya
creadas para 2024, 2025, 2026, 2027 y una `movimiento_default` para
cualquier fecha que no caiga en esas cuatro. Columnas: identificación
(`carga_id`, `cliente_id`, `encargo_id`), la fila del movimiento
(`fecha`, `num_doc`, `secuencia`, `codigo_puc`, `nombre_cuenta`, `clase`,
`cuenta`, `subcuenta`, `tercero_nit`, `tercero_nombre`, `centro_costo`,
`descripcion`, `detalle`, `debito`, `credito`, `neto`), y **`desc_norm`**
-- ya reservada para la descripción normalizada que agruparía los
74.551 movimientos en patrones, aunque esa lógica todavía no está
escrita.

Hoy los movimientos solo llegan hasta `raw.movimiento_staging`. La
promoción hacia esta tabla -- y el cuadre saldo inicial + movimientos =
saldo final por cuenta que la justifica -- sigue en la lista de
pendientes.

---

## 4. Evidencia

### `core.cotejo`
Un resumen por cada vez que se procesa una carga contra la anterior:
`resultado` (`PRIMERA_CARGA` / `ARCHIVO_IDENTICO` / `SIN_FILAS_NUEVAS` /
`CON_CAMBIOS`), conteos (`n_nuevas`, `n_modificadas`, `n_eliminadas`,
`n_fuera_periodo`), `monto_fuera_periodo`, y el `mensaje` que se ve en la
pestaña Archivos.

### `core.cotejo_detalle`
Una fila por cada cambio detectado dentro de un cotejo `CON_CAMBIOS`:
`cambio` (NUEVA/MODIFICADA/ELIMINADA), `codigo_puc`, `fecha`,
`fuera_periodo`, y `valor_antes`/`valor_ahora` (jsonb -- para balance
incluyen `saldo_inicial`, `debito`, `credito`, `saldo_final`; para
movimiento, `debito`, `credito`, `descripcion`). Es la tabla que alimenta
la tabla "Ver qué cambió" de Archivos, incluyendo el cálculo en vivo de
si esa fila quedó descuadrada.

### `core.hallazgo`
Cualquier cosa que el sistema encontró y que alguien debería revisar:
`tipo` (`DESCUADRE_LINEA`, `DESCUADRE_NIVEL`, `ERROR_PROCESO`),
`severidad`, `codigo_puc`, `monto`, `descripcion`, `fila_origen`. Se llena
durante `promover_balance()` (hasta 50 descuadres de línea por carga) y
cuando falla el procesamiento en segundo plano de una carga.

### `core.alerta`
Notificaciones -- hoy solo del tipo `CAMBIO_PERIODO_CERRADO` (una fila
nueva o modificada con fecha anterior al 1 de enero del año de corte).
`canal='SIMULADO'`: el envío no llega a ningún lado todavía, solo se
marca `ENVIADA` y se registra `destinatario`/`enviada_en` -- el punto de
enganche para SMTP o Slack ya está ahí, falta conectarlo.

---

## Una tabla huérfana

`core.nota_alcance` todavía existe en la base (vacía) de un experimento
de "nota de alcance" en Variaciones que se descartó a favor de un
resumen generado en vivo desde `analisis.py`, sin persistir nada. Ningún
código la referencia hoy. Se dejó en `schema.sql` porque el objetivo de
este archivo es reflejar la base real, no una versión idealizada -- pero
si nadie la va a usar, lo sano es un `DROP TABLE core.nota_alcance;` en
vez de cargar con ella indefinidamente.

## Lo que esta base **no** tiene, a propósito

- Sin funciones ni procedimientos almacenados.
- Sin vistas.
- Sin triggers.
- Sin columnas generadas (`to_char`/`unaccent` no son `IMMUTABLE` en
  Postgres, así que ni siquiera serían viables aquí).
- Sin `CHECK` de reglas de negocio (el cuadre, la naturaleza, la
  materialidad se validan en Python). La única vez que hubo un `CHECK` de
  cuadre por línea, bloqueó un `UPDATE` corrupto durante una prueba -- lo
  cual probó que servía, pero la decisión de moverlo todo a Python ya
  estaba tomada.
