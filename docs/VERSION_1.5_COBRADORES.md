# Gestión Financiera v1.5 — cobradores y recorridos

## Objetivo

La versión 1.5 permite repartir la cobranza de una fecha entre distintos
cobradores y conservar un registro verificable de ese trabajo. Un cobrador es
solo un nombre operativo: no es un usuario del sistema y no necesita
contraseña.

## Flujo de uso

1. Abrir **Cobranza** y elegir la fecha.
2. Presionar **Preparar planillas**.
3. Crear el cobrador si todavía no existe.
4. Elegir el cobrador, buscar y marcar sus clientes.
5. Guardar el recorrido.
6. Repetir la selección para los demás cobradores.
7. Imprimir una planilla individual o todas las planillas del día.

Cada cliente solo puede estar asignado a un cobrador por fecha. Si tiene varias
ventas pendientes, aparece una sola vez en la selección y en la hoja, con el
importe combinado y el detalle de sus operaciones.

## Registro automático

Cuando se registra un pago o una visita para un cliente asignado en esa fecha,
el sistema vincula automáticamente el movimiento con el recorrido y el
cobrador. El usuario no vuelve a elegir el cobrador durante el cobro.

El historial de **Cobranza → Historial de cobradores** informa:

- fechas con recorridos guardados;
- cantidad de asignaciones;
- clientes diferentes;
- importe previsto al preparar cada planilla;
- dinero efectivamente cobrado mediante pagos vigentes;
- clientes asignados con mayor frecuencia;
- detalle de pagos atribuidos.

“Días trabajados” significa fechas con al menos un recorrido guardado. El
sistema no intenta afirmar si el cobrador completó físicamente toda la ruta.

## Integridad y auditoría

- La base impide duplicar un cliente entre cobradores en la misma fecha.
- Una asignación con pagos o visitas registrados no puede quitarse ni moverse.
- La planilla conserva una copia del nombre, domicilio, teléfono, operaciones,
  atraso e importe esperado que existían al preparar el recorrido.
- Un pago anulado deja de sumar en el total cobrado del cobrador, pero mantiene
  su registro histórico en la venta.
- **Borrar cobrador** lo envía a Configuración → Archivo seguro. Deja de estar
  disponible para recorridos nuevos, pero conserva todos sus días, clientes,
  planillas y cobros. El registro protegido puede abrirse para consultar el
  detalle completo.

## Portabilidad y datos

Los cobradores y recorridos viven en la misma base SQLite que clientes, ventas
y pagos. Por eso están incluidos automáticamente en copias de seguridad,
restauraciones y traslado de la carpeta portable.

La exportación agrega:

- `cobradores.csv`;
- `recorridos_cobranza.csv`;
- `asignaciones_cobranza.csv`;
- identificadores de cobrador y asignación en `pagos.csv` e
  `intentos_cobranza.csv`.

## Compatibilidad

Las migraciones `0012_collectors_and_collection_routes.py` y
`0013_collector_safe_archive.py` solo agregan tablas y columnas opcionales. Las
bases de versiones anteriores se actualizan sin
modificar clientes, ventas, cuotas, recargos, pagos ni visitas existentes. Los
movimientos anteriores quedan sin cobrador, porque esa información no existía.

La planilla diaria anterior se conserva internamente para compatibilidad. El
botón visible de Cobranza abre el nuevo preparador por cobrador.

## Datos ficticios portables

La carpeta portable incluye tres archivos numerados:

1. `1_CARGAR_DATOS_FICTICIOS.bat`: guarda primero una copia verificada de la
   base actual y después carga 50 clientes, 70 ventas y 5 cobradores.
2. `2_LIMPIAR_BASE_DE_PRUEBA.bat`: respalda la demostración y deja la base de
   trabajo vacía, sin tocar la copia original protegida.
3. `3_RESTAURAR_BASE_ORIGINAL.bat`: recupera la base guardada por el primer
   archivo y cierra la sesión de prueba.

Los tres se niegan a trabajar mientras el sistema está abierto. La copia
original queda en `storage\datos_prueba` y se verifica con SHA-256 antes de
restaurarla.

## Validación de esta versión

- 281 pruebas aprobadas.
- 7 pruebas de préstamos omitidas porque la edición estable 01/08 no habilita
  ese módulo.
- Ruff sin observaciones.
- `manage.py check` sin errores.
- `makemigrations --check --dry-run` sin cambios pendientes.
