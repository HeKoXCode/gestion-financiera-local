# Fase 3: interfaz comercial

Versión: 1.0  
Estado: terminada  
Fecha: 23/07/2026

## Objetivo

Convertir los modelos de la Fase 2 en una aplicación utilizable para consultar
un día, administrar clientes y productos, y registrar ventas financiadas con
sus cuotas.

## Sistema visual

La interfaz funciona completamente offline y no descarga tipografías,
iconografía ni estilos desde Internet.

Se definió un sistema visual común:

- navegación verde oscuro;
- fondo cálido de bajo contraste;
- tarjetas blancas y bordes suaves;
- color verde para acciones principales;
- ámbar para avisos;
- rojo para atrasos y cancelaciones;
- importes alineados y con formato argentino;
- botones y formularios amplios;
- estados identificables por texto y color;
- foco visible para navegación con teclado;
- reducción de animaciones si Windows así lo solicita.

En equipos de escritorio se utiliza una barra lateral. En pantallas pequeñas:

- la navegación pasa a ser horizontal;
- las estadísticas se reorganizan;
- los formularios pasan a una columna;
- las tablas se convierten en fichas con etiquetas;
- los botones mantienen un tamaño cómodo para uso táctil.

## Pantalla diaria

La portada permite seleccionar cualquier fecha y muestra:

- accesos a los días de lunes a sábado;
- clientes a visitar;
- monto programado;
- clientes atrasados;
- deuda atrasada;
- cuota, producto, domicilio y vencimiento;
- estado “Vence hoy” o cantidad de días de atraso;
- acceso al cliente y a la venta.

Esta pantalla adelanta una parte de la Fase 5. En la Fase 4 se conectará con la
generación automática de recargos y el registro de pagos.

## Clientes

Se implementó:

- listado paginado;
- búsqueda por nombre, DNI, teléfono, dirección o barrio;
- filtros activos, archivados y todos;
- alta;
- edición;
- detalle personal y domicilio;
- historial de ventas y saldos;
- preselección del cliente al iniciar una venta;
- archivado y reactivación.

Archivar no elimina datos y tampoco modifica sus ventas anteriores.

## Productos

Se implementó:

- catálogo en tarjetas;
- búsqueda;
- filtros por estado;
- alta;
- edición;
- archivado y reactivación;
- cantidad de ventas asociadas.

Editar un producto no cambia la descripción congelada en ventas anteriores.

## Ventas

El formulario contiene:

- cliente;
- producto;
- descripción específica;
- fecha de entrega;
- precio del producto;
- entrega inicial y método de pago;
- total en cuotas;
- frecuencia semanal, quincenal o mensual;
- cantidad de cuotas;
- primer día de cobro.

El **precio del producto** es el valor acordado. La **entrega inicial** es el
dinero recibido al entregar el producto. El **total en cuotas** es lo que se
divide entre las cuotas y puede ser distinto del saldo base si se acordó un
costo financiero o un descuento; no incluye futuros recargos por atraso.

Por defecto, el total en cuotas se recalcula en cada cambio como precio menos
entrega inicial y el servidor vuelve a calcularlo al guardar. Para usar otro
importe es obligatorio activar explícitamente “Usar un total en cuotas
diferente”; así un valor escrito anteriormente no puede conservarse por error.

Mientras se completa, una vista previa local muestra:

- número de cada cuota;
- vencimiento;
- importe;
- frecuencia;
- precio, entrega, saldo base y total de la operación;
- ajuste de centavos de la última cuota.

Al confirmar:

1. se valida la operación;
2. se copia el recargo configurado;
3. se congela la descripción del producto;
4. se guarda la venta;
5. se registra la entrega inicial como dinero recibido, cuando corresponda;
6. se crean todas las cuotas en una única transacción;
7. se abre el detalle de la operación.

## Detalle y estados

El detalle de una venta muestra:

- cliente y producto;
- precio del producto;
- entrega inicial;
- total en cuotas;
- total pendiente y recibido;
- frecuencia;
- recargo diario congelado;
- capital y recargos pendientes;
- cronograma completo;
- estado de cada cuota.

Una venta activa puede cancelarse indicando un motivo. La cancelación conserva
el historial y las cuotas, pero impide que vuelva a la pantalla diaria.

El estado “Finalizada” se activará automáticamente en la Fase 4 cuando todas
las cuotas queden canceladas.

## Validaciones

- solo clientes y productos activos aparecen en ventas nuevas;
- no se guarda una venta sin sus cuotas;
- cantidad máxima según Configuración;
- primer cobro no anterior a la entrega;
- frecuencias habilitadas;
- importes positivos y exactos;
- descripción automática si se deja vacía;
- ventas canceladas requieren motivo;

En una frecuencia mensual se conserva el día del primer vencimiento. Cuando ese
día no existe en un mes, la cuota vence el último día de ese mes y el siguiente
mes vuelve al día original cuando sea posible.
- acciones de archivar y cancelar usan solicitudes protegidas;
- el formulario desactiva el botón tras enviarlo para reducir dobles cargas.

## Archivos principales

```text
app/modules/core/forms.py
app/modules/core/views.py
app/modules/core/urls.py
app/templates/base.html
app/templates/core/home.html
app/templates/core/customers/
app/templates/core/products/
app/templates/core/sales/
app/static/css/app.css
app/static/js/sale-form.js
```

## Verificación

```text
46 pruebas aprobadas
Cobertura: 92 %
Django check: sin errores
Ruff: sin errores
Migraciones pendientes: ninguna
JavaScript: sintaxis válida
```

Los casos automáticos cubren el resumen diario, formularios, búsquedas,
edición, archivado, dependencias de venta, límite de cuotas, creación del
cronograma, detalle y cancelación sin pérdida de historial.

## Próximo paso

Fase 4: cobranza, pagos completos y parciales, anulación, intentos de cobranza,
actualización automática de estados y enlace manual a WhatsApp.
