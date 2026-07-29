# Fase 0: reglas financieras del MVP

Versión: 1.0  
Estado: cerrada para implementación  
Alcance: aplicación local monousuario

Estas reglas son la fuente de verdad para los cálculos del sistema. Si una
regla cambia, se actualizarán primero este documento y sus pruebas automáticas.

## 1. Vencimiento y atraso

1. La cuota no tiene recargo durante su fecha de vencimiento.
2. El primer recargo se genera al día siguiente del vencimiento.
3. Los días de atraso se calculan por días calendario.
4. Domingos y feriados generan recargo en la configuración inicial.
5. Un pago realizado después del día de vencimiento incluye el recargo del día
   en que se registra.
6. Solo se genera un recargo por cuota y fecha.

La opción de cobrar domingos queda disponible en Configuración. El MVP no
mantendrá un calendario especial de feriados: se consideran días calendario.

## 2. Recargo

1. El recargo es un importe fijo diario por cuota, no un porcentaje.
2. El importe configurado al crear la venta queda copiado en ella.
3. Cambiar el recargo general solo afecta ventas nuevas.
4. El recargo continúa mientras exista cualquier saldo en la cuota.
5. Después de un pago parcial continúa aplicándose el importe diario completo;
   no se prorratea por el saldo restante.
6. Una venta finalizada o cancelada no genera nuevos recargos.

Ejemplo:

```text
Cuota original:       $20.000
Recargo diario:        $5.000

Vencimiento:           $20.000
1 día de atraso:       $25.000
2 días de atraso:      $30.000
3 días de atraso:      $35.000
```

## 3. Aplicación de pagos

1. Se atiende primero la cuota vencida más antigua.
2. Dentro de cada cuota se pagan primero los recargos y después el capital.
3. Si sobra importe, se continúa con la siguiente deuda exigible.
4. En la configuración inicial no se permiten pagos adelantados.
5. Tampoco se permite pagar más que la deuda exigible.
6. Los pagos parciales están permitidos.
7. Los importes se calculan con dos decimales exactos; nunca con números de
   punto flotante.
8. La última cuota absorbe cualquier diferencia de centavos.

La posibilidad de admitir pagos adelantados queda como opción de configuración,
pero permanecerá desactivada hasta implementar y probar expresamente ese flujo.

## 4. Anulación de pagos

1. Un pago registrado no se elimina.
2. Para corregirlo se marca como anulado y se solicita un motivo.
3. Un pago anulado deja de descontarse del saldo.
4. Se conservan su fecha, importe, aplicaciones y momento de anulación.

## 5. Estados de venta

- **Activa:** participa de agenda, cobranza, saldos exigibles y recargos.
- **Finalizada:** todas sus cuotas fueron canceladas; conserva el historial.
- **Cancelada:** la operación se deja sin efecto, conserva sus datos y pagos,
  pero deja de aparecer en la cobranza y no genera nuevos recargos.

Cancelar no significa borrar. Se exigirá una fecha y un motivo. El saldo
histórico seguirá siendo consultable, aunque no contará como deuda exigible.

## 6. Intentos de cobranza

Registrar “No pagó”, “Ausente” o “Prometió pagar” crea una anotación, pero no
modifica la deuda, el vencimiento ni el recargo.

## 7. Configuración inicial

```text
Recargo diario:                  $5.000
Cobranza:                        lunes a sábado
Domingos generan recargo:        sí
Recargo tras un pago parcial:    sí
Pagos adelantados:               no
Frecuencias:                     semanal, quincenal y mensual
Máximo de cuotas:                60
Métodos:                         efectivo, transferencia y otro
```

Los días disponibles de cobranza indican cuándo trabaja el cobrador; no
modifican por sí solos el cálculo de días de atraso.

## 8. Datos anteriores

Se asume que la primera versión comienza sin importación automática de datos
históricos. Los datos existentes podrán cargarse manualmente. Si más adelante
se entrega una planilla de origen, la importación se tratará como una tarea
separada para no interpretar columnas o saldos de forma incorrecta.

## 9. Criterios de aceptación

La Fase 0 se considera cerrada cuando:

- todas las reglas anteriores tienen pruebas automáticas en el motor;
- ningún recargo puede duplicarse;
- un pago anulado no reduce la deuda;
- los pagos parciales conservan su saldo;
- una venta cancelada no vuelve a la cobranza;
- toda modificación futura de estas reglas actualiza también sus pruebas.
