# Préstamos integrados — 06/08/2026

Los préstamos se implementaron como un tipo de operación dentro del módulo
Ventas. No se crean como productos ficticios: de ese modo el catálogo y el
ranking de productos vendidos conservan información correcta.

## Uso

1. Abrir `Ventas` y elegir `Nueva operación`.
2. Seleccionar `Préstamo de dinero`.
3. Buscar al cliente.
4. Indicar capital entregado y si se entregó por efectivo, transferencia u otro
   medio configurado.
5. Indicar el interés total, la frecuencia, la cantidad de cuotas y el primer
   vencimiento.
6. Revisar el total a devolver y el calendario antes de confirmar.

El interés es un porcentaje único sobre el capital. Por ejemplo, $100.000 al
20% genera un total a devolver de $120.000. No representa una tasa mensual.

Cuando el acuerdo ya tiene un importe final, se puede activar `Usar otro total a
devolver`. El sistema calcula y guarda el porcentaje efectivo. También se puede
indicar el monto de cada cuota; cantidad por monto determina el total.

## Integración

El préstamo reutiliza el motor probado de cuotas, vencimientos, recargos,
pagos completos o parciales, carga histórica, cobranza, agenda semanal,
historial del cliente, resumen PDF, planilla diaria y copias de seguridad.

Los reportes financieros incluyen los saldos del préstamo. Además muestran
cantidad de préstamos, capital entregado, total acordado y saldo pendiente. Los
préstamos quedan excluidos del ranking de productos más vendidos.

La exportación `ventas.csv` agrega tipo de operación, medio de entrega e interés
del préstamo, manteniendo las columnas anteriores para conservar compatibilidad.

## Reglas de integridad

- Una venta de producto debe tener producto.
- Un préstamo no puede tener producto ni pago inicial.
- Todo préstamo debe indicar cómo se entregó el dinero.
- El total a devolver no puede ser inferior al capital.
- Los importes finales se recalculan en el servidor antes de guardar.

La migración `0007` agrega estos datos sin modificar las ventas anteriores, que
continúan identificadas como ventas de producto.
