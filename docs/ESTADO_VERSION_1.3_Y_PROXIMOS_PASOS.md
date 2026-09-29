# Gestión Financiera v1.3 — definición y estado

Fecha: 24/08/2026<br>
Base utilizada: v1.2.2-edicion01ago

## Actualización 1.3.2: ventas canceladas solo en Archivo seguro

- El cliente, la impresión, el PDF y el envío por WhatsApp omiten por completo
  las operaciones canceladas y todos sus movimientos relacionados.
- Los totales, conteos, Cobranza, Semana, Inicio y Reportes tampoco las incluyen,
  aunque se elija una fecha anterior a la cancelación.
- La venta, sus cuotas, pagos, visitas y motivo permanecen íntegros y de solo
  lectura en Configuración → Archivo seguro.

## Actualización 1.3.1: pagos adelantados

- Cobranza incorpora un buscador específico para adelantos.
- Cliente → Venta muestra el plan semanal, cada 2 semanas o mensual y permite
  adelantar la próxima cuota desde su propia fila.
- El pago queda identificado como “Pago adelantado” en todos los historiales.
- El cronograma no se desplaza y no se otorgan días de gracia.
- Los pagos normales quedaron aislados de las cuotas futuras para impedir una
  aplicación accidental.

## Definición aprobada

La v1.3 conserva el cronograma fijo de v1.2.2 y corrige la superposición de
recargos:

- todas las cuotas vencidas suman su capital pendiente;
- la cuota impaga más antigua determina los días generales de atraso;
- existe un solo recargo por día para toda la venta;
- una segunda cuota vencida no genera una segunda cadena de recargos;
- el historial sí muestra el atraso individual de cada cuota;
- los pagos se distribuyen desde la deuda más antigua y pueden cubrir varias
  cuotas vencidas.

Ejemplo aprobado:

```text
Cuota 1: $20.000 y 10 días de atraso
Cuota 2: $20.000 y  3 días de atraso

Capital:  $40.000
Recargo:  10 × $5.000 = $50.000
Total:    $90.000
```

Los 3 días de la cuota 2 se informan, pero no agregan otro recargo porque están
incluidos en los 10 días durante los cuales la venta ya estaba atrasada.

## Cambios técnicos

1. `get_due_sale_balance` y Cobranza vuelven a sumar todas las cuotas vencidas.
2. El motor agrupa recargos por venta y fecha, no por cuota y fecha.
3. Los pagos pueden distribuir capital entre varias cuotas ya vencidas.
4. El historial conserva los días individuales de cada cuota.
5. Configuración conserva el importe diario, la opción de domingos y la regla
   posterior a pagos parciales.
6. La migración deja sin efecto cargos diarios superpuestos sin borrar filas.
7. La planilla conserva hasta 10 clientes por hoja A4.
8. Los pagos retroactivos recalculan la cadena diaria posterior.

## Actualización desde v1.2.2

La migración `0010_single_daily_late_fee_policy` agrega a cada recargo:

- `waived_amount`: parte que deja de integrar la deuda;
- `waived_reason`: explicación de la superposición;
- `waived_at`: fecha de normalización.

Si v1.2.2 guardó el mismo día en dos cuotas de una venta, v1.3 mantiene una
sola suma diaria efectiva. Las demás filas permanecen visibles en la auditoría
y en el CSV.

## Pruebas obligatorias

- dos cuotas vencidas suman ambos capitales;
- 10 y 3 días de atraso producen sólo 10 recargos diarios;
- el resultado de $40.000 + $50.000 es $90.000;
- cada cuota conserva 10 y 3 días en el historial;
- dos filas antiguas de una misma venta y fecha no duplican la deuda;
- un pago completo se distribuye entre ambas cuotas;
- un pago parcial agrega como máximo un cargo por el día siguiente;
- domingos y continuidad tras pago parcial respetan Configuración;
- la migración real desde v1.2.2 conserva todas las filas históricas.

Resultado de cierre: 256 pruebas aprobadas, 7 omitidas por corresponder al
módulo de préstamos no incluido en esta edición y 87 % de cobertura automática.

## Criterio para instalar al cliente

1. Cerrar el sistema.
2. Crear una copia restaurable.
3. Conservar el ZIP de v1.2.2.
4. Aplicar la actualización sin reemplazar `data`, `backups`, `exports`,
   `media` ni `storage`.
5. Abrir una venta con dos cuotas vencidas.
6. Confirmar que Cobranza sume ambos capitales y un solo recargo diario.
7. Comparar el total con la fórmula documentada antes de registrar pagos.
