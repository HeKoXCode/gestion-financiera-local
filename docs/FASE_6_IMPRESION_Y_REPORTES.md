# Fase 6: impresión, reportes y configuración

Estado: terminada el 24/07/2026.

## Objetivo

Completar la salida operativa de la aplicación:

1. una planilla diaria preparada para imprimir en A4;
2. reportes que expliquen cobranza, mora y cartera;
3. configuración editable para personalizar el negocio y las impresiones.

Todo funciona localmente y no requiere Internet, Power BI ni un generador de
PDF externo.

## Planilla diaria

Se agregó la ruta:

```text
/cobranza/planilla/?fecha=AAAA-MM-DD
```

Puede abrirse desde Cobranza o Reportes. La vista incluye:

- nombre y logo del negocio;
- día y fecha seleccionados;
- cantidad de clientes y registros;
- monto total esperado;
- nombre, dirección, barrio y teléfono;
- referencia del domicilio;
- producto y cuota de origen;
- días de atraso;
- capital, recargos y deuda total;
- espacio de firma;
- espacio de observaciones.

La deuda se obtiene del mismo servicio utilizado por Cobranza. Los pagos
parciales, recargos y anulaciones se reflejan automáticamente.

El botón `Imprimir` abre el diálogo del navegador. Desde allí también puede
elegirse `Guardar como PDF`.

## Verificación A4

La plantilla se imprimió automáticamente con 18 clientes de prueba y luego se
renderizó nuevamente como imágenes para revisar el resultado.

Resultado:

```text
Tamaño: A4 vertical
Clientes: 18
Páginas: 4
Fichas cortadas entre páginas: ninguna
Superposiciones: ninguna
Espacios de firma y observaciones: legibles
```

La versión revisada utiliza colores suaves que mantienen buena lectura incluso
si se imprime en escala de grises.

## Reportes

Se agregó la ruta:

```text
/reportes/
```

La fecha de corte puede modificarse. Los indicadores muestran:

- cobrado en la fecha;
- cobrado desde el lunes de la semana;
- cobrado desde el primer día del mes;
- total pendiente de la cartera;
- deuda exigible;
- deuda vencida;
- clientes morosos;
- clientes al día;
- ventas con saldo;
- evolución de cobranza de los últimos siete días;
- importes del mes por método de pago.

También se incluyen:

- clientes morosos ordenados por deuda vencida;
- clientes con mayor deuda total, incluidas cuotas futuras;
- clientes con financiación activa sin atraso;
- productos más vendidos;
- total en cuotas y pendiente por producto.

Los pagos anulados y las ventas canceladas quedan fuera de los totales.

## Configuración

Se habilitó la opción `Configuración` del menú. Permite modificar:

- nombre del negocio;
- logo PNG, JPG o WEBP;
- recargo diario para ventas nuevas;
- días habilitados para cobranza;
- métodos de pago;
- frecuencias;
- cantidad máxima de cuotas;
- recargos de domingos;
- comportamiento después de pagos parciales;
- pagos adelantados;
- mensaje manual de WhatsApp.

Los logos se guardan en `media/` y el lanzador local puede mostrarlos también
cuando se ejecuta en modo final.

## Criterios de cálculo

- Los períodos terminan en la fecha de corte seleccionada.
- La semana comienza el lunes.
- La cartera pendiente incluye cuotas futuras.
- La deuda exigible incluye cuotas vencidas y las que vencen en la fecha.
- La deuda vencida incluye solamente vencimientos anteriores.
- “Cliente al día” significa que conserva saldo financiado, pero no tiene
  cuotas vencidas.
- Las ventas canceladas no integran cartera ni rankings.
- Los pagos anulados no integran cobranza.

## Verificación automatizada

Se agregaron pruebas para:

- totales de día, semana y mes;
- separación entre cartera, deuda exigible y deuda vencida;
- pagos parciales;
- exclusión de ventas canceladas;
- clientes al día;
- ranking de productos;
- pantalla de reportes;
- planilla con y sin cobranza;
- modificación de configuración;
- validación del formato del logo;
- entrega del CSS de impresión desde el lanzador local.

Resultado:

```text
94 pruebas aprobadas
Cobertura: 92 %
Django check: sin errores
Ruff: sin errores
Migraciones pendientes: ninguna
Integridad SQLite: ok
```

## Próxima fase

Fase 7: completar exportación ZIP/CSV, retención de backups, restauración
externa y controles de recuperación.
