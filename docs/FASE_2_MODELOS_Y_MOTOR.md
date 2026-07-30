# Fase 2: modelos y motor financiero base

Versión: 1.0  
Estado: terminada  
Fecha: 23/07/2026

## Objetivo

Construir la estructura relacional y los servicios financieros sobre los que
funcionarán las pantallas de clientes, ventas y cobranza.

## Modelos implementados

| Modelo | Responsabilidad |
| --- | --- |
| Configuración | Parámetros únicos del sistema |
| Cliente | Datos personales, domicilio y estado |
| Producto | Catálogo simple de artículos |
| Venta | Condiciones financiadas y recargo congelado |
| Cuota | Número, vencimiento e importe original |
| Recargo | Importe diario asociado a una cuota y fecha |
| Pago | Cabecera del ingreso de dinero |
| Aplicación de pago | Distribución entre cuota, recargo y capital |
| Intento de cobranza | No pagó, ausente, prometió pagar u otro |

Relación principal:

```text
Cliente
|-- Ventas
|   |-- Cuotas
|   |   |-- Recargos
|   |   `-- Aplicaciones de pago
|   |-- Pagos
|   `-- Intentos de cobranza
`-- Historial consolidado
```

## Restricciones de integridad

- DNI único cuando fue informado; varios clientes pueden no tener DNI.
- Nombre de producto único.
- Importes de ventas, cuotas, pagos y aplicaciones mayores que cero.
- Recargos generales y congelados nunca negativos.
- Número de cuota único dentro de cada venta.
- Un solo recargo por cuota y fecha.
- Una sola aplicación por pago, cuota y componente.
- El cliente de un pago debe coincidir con el cliente de la venta.
- La cuota de una aplicación debe pertenecer a la venta del pago.
- Una venta cancelada requiere fecha y motivo.
- Un pago anulado requiere fecha y motivo.
- La configuración general es única y no puede eliminarse.

SQLite también se ejecuta con claves foráneas activas, tiempo de espera para
escrituras y modo WAL.

## Configuración inicial

La migración crea automáticamente una configuración con:

```text
Nombre:                           Gestión Financiera
Recargo diario:                  $5.000
Días de cobranza:                lunes a sábado
Frecuencias:                     semanal, quincenal y mensual
Máximo de cuotas:                60
Domingos generan recargo:        sí
Recargo tras pago parcial:       sí
Pagos adelantados:               no
Métodos de pago:                 efectivo, transferencia y otro
```

## Cronograma de cuotas

El servicio:

- calcula fechas cada 7 o 14 días;
- usa importes Decimal con dos posiciones;
- divide el total en cuotas sin perder centavos;
- asigna la diferencia de redondeo a la última cuota;
- respeta las frecuencias y máximo de cuotas configurados;
- evita generar las cuotas dos veces.

Ejemplo verificado:

```text
$480.000 / 12 cuotas = 12 cuotas de $40.000
```

Ejemplo de redondeo:

```text
$100 / 3 = $33,33 + $33,33 + $33,34
```

## Servicio de saldos

Puede calcular el estado de una cuota o venta en una fecha determinada:

- capital original;
- capital abonado;
- capital pendiente;
- recargos generados;
- recargos abonados;
- recargos pendientes;
- total abonado;
- total pendiente;
- días de atraso.

Solo descuenta aplicaciones pertenecientes a pagos registrados. Si un pago se
anula, deja automáticamente de reducir el saldo sin borrar su historial.

## Servicio de recargos

El generador:

1. busca cuotas vencidas de ventas activas;
2. comienza al día siguiente del vencimiento;
3. comprueba si había saldo al comenzar cada día;
4. respeta la configuración de domingos y pagos parciales;
5. usa el recargo congelado en la venta;
6. crea como máximo un registro por cuota y fecha.

Es idempotente: ejecutarlo varias veces para la misma fecha produce el mismo
resultado y no duplica importes.

## Migraciones

```text
core.0001_initial
core.0002_default_settings
```

La base real fue migrada y `PRAGMA integrity_check` respondió `ok`.

## Pruebas

Se verificaron:

- configuración predeterminada;
- días inválidos;
- DNI vacío y duplicado;
- cancelación y anulación con motivo;
- coherencia cliente–venta–pago–cuota;
- recargos duplicados;
- cronogramas semanales, quincenales y mensuales;
- redondeo de última cuota;
- recargo desde el día posterior;
- tres días de atraso;
- ejecución idempotente;
- inclusión y exclusión de domingos;
- continuidad tras pago parcial;
- interrupción configurable tras pago parcial;
- detención después del pago total;
- pago anulado;
- venta cancelada;
- saldo agregado de una venta.

Resultado al cerrar la fase:

```text
34 pruebas aprobadas
Cobertura automática: al menos 80 %
Django check: sin errores
Ruff: sin errores
Integridad SQLite: ok
```

## Próximo paso

Fase 3: formularios y pantallas para clientes, productos y ventas, usando estos
servicios para previsualizar y crear las cuotas.
