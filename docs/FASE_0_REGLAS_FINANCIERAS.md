# Fase 0 — reglas financieras definitivas de v1.3

Fecha: 24/08/2026

Este documento define la regla que deben respetar Cobranza, pagos, historial,
reportes, impresión, exportación y migración desde v1.2.2.

## 1. Cuotas vencidas

1. Las fechas del cronograma no se desplazan.
2. Toda cuota cuya fecha ya llegó integra el capital exigible mientras conserve
   saldo.
3. Si existen dos cuotas vencidas de $20.000, el capital a cobrar es $40.000.
4. La cuota pendiente más antigua determina los días generales de atraso de la
   venta.
5. En el historial, cada cuota conserva su propio vencimiento y sus propios
   días de atraso con fines informativos.

## 2. Un solo recargo diario por venta

1. El día del vencimiento no genera recargo.
2. Desde el día siguiente se suma el importe diario configurado mientras la
   venta no esté al día.
3. En una misma fecha sólo puede existir un recargo efectivo para toda la
   venta, aunque haya dos o más cuotas atrasadas.
4. El recargo no se calcula por separado para cada cuota.
5. El importe diario queda congelado al crear la venta. Cambiar Configuración
   afecta a ventas nuevas y no reescribe las anteriores.
6. La opción `Generar recargos los domingos` decide si el domingo cuenta.
7. La opción `Seguir sumando recargo después de un pago parcial` decide si la
   cadena diaria continúa mientras quede deuda.

## 3. Ejemplo aprobado

```text
Cuota 1: $20.000 — 10 días de atraso
Cuota 2: $20.000 —  3 días de atraso
Recargo diario: $5.000

Capital vencido:       $20.000 + $20.000 = $40.000
Recargo de la venta:   10 días × $5.000  = $50.000
Total a cobrar:                               $90.000
```

Los 3 días de la cuota 2 aparecen en el historial, pero no originan otros
$15.000. Esos días ya están contenidos dentro de los 10 días generales durante
los cuales la venta permaneció atrasada.

## 4. Aplicación de pagos

1. Se calcula la deuda existente en la fecha real del pago.
2. Se cubre primero el recargo diario acumulado.
3. Después se cubre el capital de las cuotas vencidas, desde la más antigua.
4. Si están vencidas varias cuotas, un mismo pago puede cubrir más de una.
5. Un pago normal nunca recibe dinero para cuotas futuras, aunque Configuración
   permita adelantos. Debe utilizarse “Registrar pago adelantado”.
6. Un pago parcial nunca duplica el recargo de una fecha ya contabilizada.

## 5. Pagos adelantados

1. Se registran con la fecha real de hoy; nunca con la fecha futura de la cuota.
2. Sólo se habilitan cuando la venta está al día. Si existe una cuota vencida o
   que vence hoy, primero se usa el pago normal.
3. Se aplican a la cuota futura impaga más cercana. Si sobra dinero, continúan
   con las siguientes en su orden original.
4. No se modifica `due_date`: ninguna semana, quincena o mes se desplaza.
5. No existen días de gracia. Un adelanto parcial deja el resto exigible en el
   vencimiento original y el recargo puede comenzar al día siguiente.
6. Desde Cliente → Venta se ofrece “Adelantar esta cuota” sólo en la próxima
   cuota disponible; las posteriores indican que primero corresponde la anterior.

## 6. Pagos retroactivos

Al registrar hoy un pago que realmente se recibió un día anterior:

1. se exige confirmación;
2. se calcula la deuda hasta aquella fecha;
3. se conserva la fecha real del movimiento;
4. se recalcula la cadena posterior de recargos;
5. los registros que dejan de corresponder no se borran: su importe queda sin
   efecto y se conserva para auditoría.

## 7. Compatibilidad con v1.2.2

La versión anterior podía generar un recargo diario para cada cuota atrasada.
La migración v1.3 agrupa por venta y fecha:

- conserva un único importe diario efectivo;
- deja sin efecto los cargos superpuestos de las otras cuotas;
- no elimina registros, pagos ni comprobantes;
- guarda importe, motivo y fecha de la normalización;
- permite exportar tanto el valor original como el vigente.

## 8. Criterios obligatorios de aceptación

- Dos cuotas vencidas de $20.000 suman $40.000 de capital.
- Diez días de atraso a $5.000 suman $50.000 de recargo.
- El ejemplo completo arroja $90.000.
- La segunda cuota muestra 3 días en el historial sin sumar otro recargo.
- Abrir el sistema repetidas veces no duplica cargos.
- Un domingo se incluye o excluye según Configuración.
- Un pago retroactivo corrige importes posteriores sin borrar el historial.
- Un adelanto completo cancela la próxima cuota sin cambiar ninguna fecha.
- Un adelanto parcial no posterga el vencimiento ni el inicio del recargo.
