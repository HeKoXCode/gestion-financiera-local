# Fase 5: dashboard, agenda e historial

Estado: terminada el 24/07/2026.

## Objetivo

Convertir los datos de ventas, cuotas, recargos, pagos y visitas en tres
pantallas operativas:

1. un dashboard para decidir qué cobrar;
2. una agenda semanal para organizar el recorrido;
3. un historial de cliente que concentre toda su actividad.

La fase no agrega infraestructura, usuarios ni servicios externos. Todo sigue
funcionando localmente con Django y SQLite.

## Dashboard

La pantalla inicial ahora muestra para la fecha seleccionada:

- clientes con deuda exigible;
- monto restante por cobrar;
- clientes y monto en mora;
- dinero cobrado en la fecha;
- cartera pendiente completa, incluidas cuotas futuras;
- porcentaje de avance respecto del objetivo del día;
- cantidad de ventas activas;
- cuotas que vencen en los próximos siete días;
- visitas de cobranza registradas;
- últimos cinco pagos.

Las cobranzas se agrupan por venta. Si una venta tiene varias cuotas exigibles,
se presenta una sola fila con el total pendiente. El orden prioriza mayor
atraso y luego el nombre del cliente.

El dashboard permite cambiar rápidamente entre lunes y sábado. Una consulta
histórica respeta los pagos existentes hasta esa fecha y no ofrece registrar
un pago en una venta que actualmente ya está finalizada.

## Agenda semanal

Se agregó la ruta:

```text
/agenda/
```

La fecha puede elegirse desde el selector o desde la banda semanal. La agenda
separa:

- **Programadas:** ventas con al menos una cuota cuyo vencimiento coincide con
  la fecha;
- **Arrastre:** deuda de días anteriores que todavía no fue saldada.

También resume:

- clientes incluidos en el recorrido;
- cantidad de cuotas programadas;
- importe programado;
- total exigible del recorrido;
- distribución por barrio.

Las filas dan acceso directo al detalle de la venta y la pantalla se adapta a
escritorio, tablet y celular.

## Historial consolidado del cliente

El detalle del cliente ahora reúne:

- datos personales y administrativos;
- total financiado no cancelado;
- total abonado mediante pagos vigentes;
- saldo pendiente;
- cantidad de cuotas atrasadas y pagadas;
- todas las ventas y productos;
- todas las cuotas y su estado;
- pagos registrados y anulados;
- visitas e intentos de cobranza;
- línea de tiempo de ventas, cancelaciones, pagos y visitas.

Una venta cancelada permanece visible para conservar la trazabilidad, pero su
saldo se muestra como no exigible. Un pago anulado también permanece en el
historial, aunque no integra el total abonado.

## Diseño

Se mantuvo el lenguaje visual de las fases anteriores:

- verde oscuro para navegación y cartera;
- verde claro para acciones y estados correctos;
- ámbar para advertencias;
- rojo para mora y anulaciones;
- tarjetas compactas, tipografía legible y jerarquía visual consistente.

Las nuevas pantallas incluyen variantes responsive específicas para anchos de
74, 58 y 43 rem.

## Servicios agregados

```text
app/modules/core/services/dashboard.py
app/modules/core/services/customer_history.py
```

Los cálculos se concentran en servicios para que puedan reutilizarse en los
reportes de la Fase 6 y probarse sin depender del HTML.

## Verificación

Se agregaron pruebas para:

- objetivo diario y progreso de cobranza;
- pagos parciales en el dashboard;
- cartera con cuotas futuras;
- agenda de una fecha seleccionada;
- semana de lunes a sábado;
- historial de ventas, pagos y visitas;
- exclusión contable de pagos anulados;
- trazabilidad de ventas canceladas;
- estados de cuotas atrasadas.

Resultado final:

```text
81 pruebas aprobadas
Cobertura: 92 %
Django check: sin errores
Ruff: sin errores
Migraciones pendientes: ninguna
```

## Próxima fase

Fase 6: planilla diaria lista para imprimir en A4 y reportes de cobrado,
morosidad, cartera, productos y clientes.
