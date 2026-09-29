# Diagnóstico de ventas — edición estable 01/08

## Evidencia recibida

Se analizaron la base activa y todos los respaldos incluidos en
`GestionFinanciera.rar`. Todas las bases superaron `PRAGMA integrity_check`.

La secuencia comprobada fue:

| Momento del respaldo | Clientes | Productos | Ventas | Cuotas | Pagos |
|---|---:|---:|---:|---:|---:|
| Cierre 19/08 | 96 | 69 | 0 | 0 | 0 |
| Inicio 20/08 20:20 | 96 | 80 | 1 | 30 | 3 |
| Inicio 20/08 20:24 | 96 | 80 | 2 | 60 | 5 |
| Inicio 20/08 21:27 | 98 | 80 | 2 | 60 | 5 |
| Cierre 20/08 22:39 | 98 | 80 | 2 | 60 | 5 |

No existe evidencia de que un cierre, un inicio o una migración haya eliminado
ventas. Tampoco fue ejecutada la herramienta `ArchivarYReiniciar`, porque no
apareció el respaldo que esa operación genera y la base no quedó vacía.

## Fallo reproducido

El servidor local permitía procesar varios pedidos al mismo tiempo. Al enviar
dos ventas casi simultáneas desde ventanas diferentes, una se guardaba y la otra
terminaba con HTTP 500 y `django.db.utils.OperationalError: database is locked`.
La transacción fallida se revertía completa; por eso no quedaba una venta parcial.

Abrir varias pestañas y trabajar de manera secuencial no pierde datos. El problema
aparece cuando dos escrituras coinciden en el tiempo. En el ejecutable original,
el botón cambiaba a “Volver a abrir el sistema” y creaba otra pestaña cada vez.

## Correcciones incorporadas

1. Las solicitudes que modifican información se procesan en una cola dentro del
   servidor local.
2. Las transacciones SQLite reservan el escritor desde su comienzo y esperan hasta
   20 segundos si otra operación está terminando.
3. Después de la primera apertura, el botón indica “Sistema abierto”. Si se vuelve
   a presionar, explica que debe buscarse la pestaña existente y solo abre otra si
   la persona confirma que cerró la anterior.
4. Una segunda ejecución del EXE detecta la instancia ya activa, enfoca el panel
   existente y finaliza sin abrir otra pestaña, ejecutar migraciones ni respaldos.
5. Las páginas HTML se entregan sin caché para evitar que Chrome muestre una lista
   anterior después de volver hacia atrás.
6. Los errores quedan registrados en `storage\gestion_financiera.log`, con rotación
   automática de hasta cinco archivos de 2 MB.

## Alcance

Esta edición conserva la estética verde y las funciones de ventas financiadas del
01/08. No expone ni permite registrar préstamos.
