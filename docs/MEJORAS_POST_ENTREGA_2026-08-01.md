# Mejoras posteriores a la primera entrega

Fecha de validación: 1 de agosto de 2026.

## Funciones incorporadas

### Resumen del cliente para imprimir y compartir

En `Clientes > abrir un cliente` aparecen `Compartir por WhatsApp`, `Guardar
resumen PDF` e `Imprimir resumen`. El PDF contiene nombre, ventas, cuotas,
vencimientos, recargos, pagos y saldo. No incluye DNI, teléfono, domicilio,
observaciones internas, visitas, medios de pago ni motivos internos de anulación.

En un celular compatible se comparte el archivo mediante el menú del sistema. En
una computadora se descarga el PDF y se abre el chat del teléfono guardado para
que la persona lo adjunte. No se envía nada sin una acción explícita.

### Carga correcta de ventas anteriores

La pantalla de nueva venta permite indicar cuántas cuotas anteriores ya fueron
pagadas. Cada una se registra como un pago independiente en su vencimiento
o en su fecha de pago efectiva, respetando la frecuencia semanal, cada dos semanas
o mensual.

Ejemplo: una venta de 12 cuotas comenzó hace 12 semanas y el cliente pagó 11. Se
escribe `11`; las primeras 11 quedan pagadas y la cuota 12 conserva su vencimiento,
deuda y recargo reales. Las cuotas futuras no pueden marcarse como pagadas.

Al indicar la cantidad pagada aparecen botones numerados. Se tocan únicamente las
cuotas abonadas tarde y se ingresan sus días de atraso. Por ejemplo, `2: 3 días` y
`7: 1 día`. Las restantes se consideran pagadas en fecha. El historial interno,
la hoja imprimible y el PDF muestran `Pagada con N días de atraso`; además, el pago
histórico incluye los recargos generados por esos días.

Los números siempre responden al tocarlos. Si una cuota vence hoy, todavía es
futura o ya figura pagada en la entrega, se muestra inmediatamente el motivo por
el cual no puede tener días de atraso. Las cuotas pagadas en fecha aparecen
verdes con una tilde, las marcadas con atraso aparecen en amarillo y las que aún
no vencieron se muestran grises y con borde punteado.

### Búsqueda en la nueva venta

Los campos Cliente y Producto ahora combinan búsqueda y selección en un solo
cuadro. Al tocarlo muestran todas las opciones y al escribir filtran por nombre,
DNI, domicilio o descripción. Crear un cliente o producto desde la venta vuelve
al mismo formulario, selecciona lo recién creado y recupera el borrador.

### Cálculo rápido de importes

El pago inicial aparte comienza vacío, usando el ejemplo solamente como texto de
fondo. También puede indicarse cantidad de cuotas y monto de cada cuota para que
el precio y el total en cuotas se calculen automáticamente. La opción avanzada
`Usar otro total en cuotas` quedó al final del bloque de importes.

### Cuota 1 el día de la entrega

La casilla `La cuota 1 vence el día de la entrega` copia ambas fechas y obliga a
indicar si esa cuota fue pagada o quedó pendiente. Si fue pagada se registra un
pago real y separado del pago inicial. Si quedó pendiente aparece en Cobranza;
el recargo comienza al día siguiente.

## Compatibilidad con la base existente

Estas mejoras no cambian las tablas de la base de datos. Son compatibles con los
clientes, ventas, cuotas, pagos, copias y configuración que el cliente ya posee.

Para actualizar una instalación existente no se deben borrar ni reemplazar las
carpetas `data`, `backups`, `exports`, `media` y `storage`. Primero se debe cerrar
el sistema, crear una copia de seguridad y conservar otra copia externa.

## Controles realizados

- revisión visual real del formulario de venta y del resumen A4;
- prueba de búsqueda con más de 200 clientes;
- ventas históricas semanales, cada dos semanas y mensuales;
- rechazo de cuotas futuras informadas como pagadas;
- cálculo dinámico de precio, pago inicial, total en cuotas y fechas;
- vencimiento el mismo día sin recargo y recargo correcto al día siguiente;
- cuota 1 pagada y pago inicial registrados por separado el mismo día;
- privacidad del resumen destinado al cliente;
- PDF A4 de una y varias páginas;
- vista de escritorio y celular sin desbordes;
- suite integral: 205 pruebas aprobadas y 88 % de cobertura.
