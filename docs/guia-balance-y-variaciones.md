# Guia para leer el balance y las variaciones

Esta guia explica que muestran las pestanas **Balance** y **Variaciones**. Sirve para orientar la revision; no reemplaza el juicio profesional ni la evidencia del encargo.

## Naturaleza del saldo

Cada cuenta tiene un lado contable esperado. El sistema convierte el saldo a esa perspectiva para que el mismo hecho se lea igual aunque el archivo de origen use signos distintos.

| Clase PUC | Naturaleza esperada | Que significa un saldo positivo en Naturaleza |
| --- | --- | --- |
| 1 Activo | Debito | El activo esta en su lado normal. |
| 2 Pasivo | Credito | La obligacion esta en su lado normal. |
| 3 Patrimonio | Credito | El patrimonio esta en su lado normal. |
| 4 Ingresos | Credito | El ingreso esta en su lado normal. |
| 5 Gastos | Debito | El gasto esta en su lado normal. |
| 6 Costos de venta | Debito | El costo esta en su lado normal. |
| 7 Costos de produccion u operacion | Debito | El costo esta en su lado normal. |

Una cuenta puede tener una excepcion definida en el catalogo PUC. En ese caso se usa la naturaleza de la excepcion mas especifica; de lo contrario, hereda la de su clase.

Un valor negativo en la columna **Naturaleza** significa que el saldo esta al lado contrario del esperado. Es una senal para revisar, no prueba por si sola de un error: un banco sobregirado o un anticipo a proveedores pueden ser situaciones validas segun los hechos.

### Saldo final frente a Naturaleza

**Saldo final** conserva el signo con el que llego el archivo, porque asi se valida que el balance completo sume cero. **Naturaleza** aplica el signo esperado de la cuenta para interpretar su comportamiento. Si el archivo ya trae pasivos, patrimonio e ingresos negativos, ambas columnas pueden diferir en signo para esas clases, y eso es normal.

### Cuadre de una fila

Una fila cuadra cuando:

`saldo inicial + debito - credito = saldo final`

La columna **Cuadre** se marca en rojo cuando esa igualdad no se cumple. Esto senala una inconsistencia en la fila reportada y se debe contrastar con el archivo fuente.

## Como se calculan las variaciones

Las variaciones se calculan sobre el saldo en **Naturaleza**, no sobre el signo original del archivo. Asi, un aumento o disminucion conserva su significado economico entre ERPs que exportan signos de modo diferente.

- Las clases 1, 2 y 3 se comparan con el cierre del ano anterior.
- Las clases 4, 5, 6 y 7 se comparan con el mismo corte del ano anterior.
- Variacion = saldo actual en naturaleza - saldo comparativo en naturaleza.
- Porcentaje = variacion / valor absoluto del saldo comparativo. Si el comparativo es cero, no se calcula porcentaje.

La materialidad de ejecucion, el porcentaje de variacion y el piso de trivialidad los configura el auditor para cada encargo y fase. Si la fase no tiene una materialidad aplicable, el sistema muestra todas las cuentas pero no marca ninguna automaticamente.

## Filtros de Variaciones

| Filtro | Cuando entra una cuenta |
| --- | --- |
| **Para revisar** | Reune todas las cuentas seleccionadas por uno de los criterios de abajo. |
| **Monto** | El valor absoluto de la variacion alcanza o supera la materialidad de ejecucion. Tiene prioridad sobre los demas motivos. |
| **Comportamiento** | El porcentaje de variacion alcanza el porcentaje configurado y la variacion supera el piso de trivialidad. |
| **Nuevas** | El saldo comparativo es cero y el saldo actual no es trivial. |
| **Cerradas** | El saldo actual es cero y el comparativo no es trivial. |
| **Naturaleza** | El saldo actual, o el comparativo si la cuenta ya no existe en el actual, queda contrario a su naturaleza y no es trivial. |
| **Todas** | El universo completo de cuentas, incluidas las no seleccionadas. |

Cada cuenta recibe un unico motivo, en este orden: **Monto**, **Nueva**, **Cerrada**, **Comportamiento** y **Naturaleza**. La prioridad evita contar una misma cuenta varias veces; no significa que los demas aspectos dejen de requerir juicio profesional.

## Lo que queda fuera de la seleccion

Las cuentas no seleccionadas se separan entre las que estan por debajo del piso de trivialidad y las que no son triviales pero no alcanzan ningun criterio. La suma de sus variaciones absolutas se muestra como residuo no seleccionado. Si ese residuo supera la materialidad de la fase, se advierte que el alcance podria ser insuficiente.
