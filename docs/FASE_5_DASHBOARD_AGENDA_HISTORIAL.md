# Fase 5: dashboard, semana e historial

Estado: terminada el 24/07/2026.

## Objetivo

Convertir los datos de ventas, cuotas, recargos, pagos y visitas en tres
pantallas operativas:

1. un dashboard para decidir qué cobrar;
2. una vista semanal para comparar la carga de trabajo;
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

Las cobranzas se agrupan por venta. Cada venta presenta solamente su cuota
abierta más antigua, aun cuando también hayan pasado fechas posteriores. El
orden prioriza mayor atraso y luego el nombre del cliente.

El dashboard permite cambiar rápidamente entre lunes y sábado. Una consulta
histórica respeta los pagos existentes hasta esa fecha y no ofrece registrar
un pago en una venta que actualmente ya está finalizada.

## Vista semanal

Se agregó la ruta:

```text
/agenda/
```

La fecha elegida determina una semana de lunes a sábado. Los seis días se
muestran simultáneamente para evitar que esta pantalla repita la lista operativa
de Cobranza.

El resumen semanal muestra:

- clientes diferentes con vencimientos;
- cantidad de cuotas programadas;
- importe programado sin repetir deudas atrasadas;
- día con mayor cantidad de clientes en recorrido.

Cada tarjeta diaria muestra:

- clientes incluidos en el recorrido;
- importe que vence exactamente ese día;
- clientes atrasados;
- total exigible si se realiza el recorrido;
- cantidad de programados y de arrastre;
- barrios involucrados;
- acceso directo a la Cobranza de esa fecha.

“Programado” se suma semanalmente porque cada cuota aparece una sola vez. El
“Total recorrido” no se suma entre días, ya que una misma deuda atrasada podría
aparecer como arrastre en varias fechas. La pantalla se adapta a escritorio,
tablet y celular.

## Historial consolidado del cliente

El detalle del cliente ahora reúne:

- datos personales y administrativos;
- total en cuotas de ventas no canceladas;
- total abonado mediante pagos vigentes;
- saldo pendiente;
- cantidad de cuotas actuales atrasadas y cuotas pagadas;
- todas las ventas vigentes o finalizadas y sus productos;
- todas las cuotas de esas operaciones y su estado;
- sus pagos registrados y anulados;
- sus visitas e intentos de cobranza;
- línea de tiempo de ventas, pagos y visitas operativas.

Una venta cancelada, sus cuotas, pagos y visitas se retiran del historial
operativo y de los resúmenes que se comparten con el cliente. La trazabilidad
completa se conserva únicamente en Configuración → Archivo seguro. Un pago
anulado de una venta no cancelada permanece en el historial, aunque no integra
el total abonado.

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
- resumen simultáneo de lunes a sábado;
- semana de lunes a sábado;
- historial de ventas, pagos y visitas;
- exclusión contable de pagos anulados;
- trazabilidad de ventas canceladas;
- cada cuota atrasada con sus propios días, aunque el recargo diario se calcule
  una sola vez para toda la venta.

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
