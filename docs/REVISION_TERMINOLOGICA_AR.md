# Revisión terminológica para Argentina

## Criterio

La interfaz está pensada para una sola persona que administra ventas financiadas
y cobranzas de forma local. Por eso se priorizaron palabras:

- habituales en Argentina;
- comprensibles sin conocimientos contables ni informáticos;
- coherentes entre todas las pantallas;
- exactas respecto del cálculo que realiza el sistema;
- redactadas con voseo cuando se da una instrucción: `Creá`, `Elegí`, `Abrí`,
  `Cerrá`.

Los nombres técnicos de archivos y formatos (`ZIP`, `CSV`, `.sqlite3`) se
conservan únicamente donde son necesarios para reconocer una copia o una
exportación.

## Cambios principales

| Expresión anterior | Expresión elegida | Motivo |
| --- | --- | --- |
| Quincenal | Cada 2 semanas | El sistema genera vencimientos cada 14 días. “Quincenal” puede interpretarse como cada 15 días. |
| Entrega inicial | Pago inicial | Evita confundir el dinero recibido con la entrega física del producto. |
| Método de pago | Medio de pago | Es la denominación más natural para efectivo, transferencia u otra forma de pago. |
| Primer día de cobro | Fecha del primer cobro | El campo solicita una fecha completa, no solamente un día de la semana. |
| Capital pendiente | Cuotas pendientes / cuotas pendientes sin recargos | Explica directamente qué parte del saldo representa, sin jerga financiera. |
| Deuda exigible | Pendiente hasta la fecha | Evita una expresión jurídica y aclara el período incluido. |
| Clientes con pagos atrasados | Clientes morosos | Es la denominación solicitada para el informe específico de deuda vencida. En los resúmenes operativos se usa “Clientes atrasados”. |
| Cartera pendiente | Saldo total pendiente | Es más claro para un uso personal y conserva el mismo significado numérico. |
| Total recorrido | Total a cobrar | El dato es dinero pendiente, no distancia ni cantidad de visitas. |
| Arrastre | Pendiente de días anteriores | Explica de dónde proviene ese importe o cliente. |
| Datos guardados en este equipo | Sincronizado localmente | Es la frase elegida para indicar que la base local está disponible y actualizada. No implica sincronización con internet ni con la nube. |
| Dashboard | Resumen | Evita un anglicismo que no agrega información. |
| Backup | Copia de seguridad | Es comprensible para una persona no técnica y se usa de forma uniforme. |
| Trazabilidad | Historial completo | Mantiene el sentido sin utilizar terminología de auditoría. |
| Cronograma | Calendario de cuotas | Explica concretamente qué fechas se muestran. |

## Términos que se conservaron

| Término | Motivo |
| --- | --- |
| Cobranza | Es el nombre habitual en Argentina para la tarea de cobrar cuotas pendientes. |
| Cuota | Es breve, cotidiano y coincide con cada vencimiento del plan. |
| Recargo diario | Describe exactamente el importe agregado por cada día de atraso. |
| Pago parcial | Indica claramente que el pago no cancela todo el saldo. |
| Saldo pendiente | Es conocido y representa el dinero que todavía falta pagar. |
| Vencimiento | Es la fecha acordada para pagar una cuota. |
| Archivar / Reactivar | Explica que el cliente o producto deja de usarse sin borrar su historial. |
| Cancelar venta | Detiene la cobranza de la venta y conserva sus registros. |
| Anular pago | Corrige un pago sin borrarlo del historial, como corresponde a un registro financiero. |
| Semanal / Mensual | Coinciden con los intervalos reales de siete días y un mes calendario. |
| DNI, domicilio, barrio | Son datos y denominaciones habituales en Argentina. |

## Diferencias que conviene recordar

- `Precio del producto`: valor acordado del artículo antes de dividir el pago.
- `Pago inicial`: dinero recibido al entregar el producto.
- `Saldo del producto`: precio menos pago inicial, antes de cualquier ajuste.
- `Total en cuotas`: suma que se repartirá entre todas las cuotas.
- `Costo de financiación`: diferencia positiva entre el precio y el total que
  terminará pagando el cliente.
- `Total final de la venta`: pago inicial más total en cuotas.
- `Cuotas pendientes`: parte impaga de las cuotas, sin contar recargos.
- `Recargos pendientes`: importes acumulados por atraso que todavía no se pagaron.
- `Pendiente hasta la fecha`: cuotas vencidas o que vencen ese día; no incluye
  cuotas futuras.
- `Saldo total pendiente`: incluye cuotas vencidas y futuras de ventas vigentes.

## Coherencia de acciones

- Los botones usan verbos concretos: `Guardar pago`, `Registrar pago`,
  `Crear copia ZIP`, `Descargar`, `Anular` y `Cancelar`.
- `No pagó` registra directamente ese resultado para la fecha seleccionada.
- `Otro resultado` abre el formulario para registrar ausencia, promesa de pago
  u otra observación.
- El panel inicial usa `Abrir sistema` y `Cerrar y respaldar`, los mismos
  conceptos empleados en las explicaciones de restauración.
- El encabezado del día usa `Así viene el día`, una frase directa y cotidiana.
- `Clientes atrasados` identifica el contador operativo; `Clientes morosos`
  titula el informe detallado de deuda vencida.
