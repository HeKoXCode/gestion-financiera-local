# Informe de control: correcciones y archivo seguro

Fecha: 23/08/2026<br>
Versión: 1.2.0-edicion01ago

## Alcance

Se revisaron los cambios para borrar clientes de forma lógica, conservar las
versiones anteriores de clientes y ventas, corregir ventas con actividad bajo
un procedimiento excepcional y consultar todos esos antecedentes en detalle.

El control adversarial se realizó usando las pantallas y las solicitudes que
puede generar un navegador. No incluye la alteración manual de los archivos del
programa, de la base SQLite ni de la computadora, de acuerdo con el alcance
solicitado.

## Protecciones verificadas

- Un cliente con ventas activas no puede archivarse. La advertencia muestra y
  enlaza todas las ventas que deben resolverse primero.
- Al modificar un cliente se guarda una copia completa de sus datos anteriores,
  junto con el motivo, la fecha y el número de versión.
- Una solicitud repetida por recarga o doble envío no crea dos versiones de la
  misma corrección.
- Las ventas continúan admitiendo un máximo de dos correcciones.
- Una venta con pagos o visitas sólo puede corregirse después de habilitar la
  herramienta excepcional en Configuración y confirmar dos frases deliberadas.
- La corrección excepcional conserva los pagos y las visitas originales,
  reconstruye las cuotas y vuelve a asignar los pagos. Si el historial no puede
  encajar en las nuevas condiciones, revierte toda la operación sin dejar un
  estado intermedio.
- La habilitación excepcional se apaga automáticamente después de una
  corrección exitosa.
- Los pagos de una venta cancelada y los pagos pertenecientes a un cliente
  archivado no pueden anularse mediante enlaces directos.
- Las versiones archivadas no admiten edición ni eliminación desde la
  aplicación.
- Los textos ingresados se muestran escapados; no se ejecuta HTML o JavaScript
  almacenado en nombres, motivos u observaciones.
- Los formularios sensibles rechazan solicitudes GET y solicitudes POST sin un
  token CSRF válido.

## Pruebas realizadas

- Análisis estático con Ruff: aprobado.
- Comprobación interna de Django: cero problemas.
- Control de migraciones: no quedaron cambios de modelo sin migración.
- Pruebas automatizadas: 240 casos recopilados, 233 aprobados y 7 omitidos de
  forma intencional porque esta edición estable no incluye préstamos.
- Cobertura automática total: 86 %.
- Migración ensayada sobre una base temporal llevada primero hasta la versión
  0008 y luego a la 0009: datos previos conservados e integridad SQLite correcta.
- Revisión visual real en navegador de Configuración, Archivo, detalle de
  versiones, bloqueo de borrado, edición normal y edición excepcional.
- Revisión móvil a 390 x 844 px: sin desborde horizontal.
- Consola del navegador durante el recorrido: sin errores ni advertencias.
- Prueba del portable: ejecutables, inicio del servidor, recursos, base,
  migraciones, backup, restauración y archivo/reinicio aprobados.
- Auditoría del ZIP final: suma SHA-256 correcta, cero archivos sensibles y
  análisis de Microsoft Defender sin detecciones.
- Actualización simulada sobre la versión 1.1.0: pasó a 1.2.0 y conservó sin
  cambios los cinco sectores de datos del cliente.

## Casos maliciosos o incorrectos cubiertos

- Doble envío de un formulario.
- Acceso directo a una URL que la interfaz ya no ofrece.
- Intento de anular pagos históricos de registros archivados.
- Activación excepcional con una frase incorrecta.
- Confirmación de recálculo con una frase incorrecta.
- Cambio forzado hacia un cliente archivado.
- Cambio de condiciones que deja un pago histórico imposible de asignar.
- Contenido HTML o JavaScript dentro de datos visibles.
- Fechas, montos y estados incompatibles con el historial existente.

## Límites deliberados

- La herramienta excepcional no fuerza una contabilidad matemáticamente
  imposible. En ese caso informa el conflicto y no cambia nada.
- Los clientes pueden corregirse más de dos veces porque domicilio y teléfono
  pueden cambiar normalmente; todas las versiones quedan conservadas.
- Las ventas mantienen el límite de dos correcciones, incluso usando la
  herramienta excepcional.
- SQLite y el sistema están pensados para uso local. Las escrituras simultáneas
  se serializan y fueron probadas, pero no sustituyen una base multiusuario de
  servidor.
- El programa no incorpora usuarios y permisos internos, por decisión de alcance
  del producto. La herramienta excepcional está escondida y exige confirmación,
  pero quien tenga acceso físico al sistema puede verla.
- Los ejecutables no poseen firma Authenticode porque no hay un certificado de
  firma de código. La integridad del paquete se controla mediante su SHA-256.

## Resultado

No se encontraron fallas pendientes dentro del alcance probado. Este resultado
no significa que sea imposible hallar un error futuro: deja documentados el
alcance, las defensas verificadas y los límites conocidos para poder diagnosticar
cualquier incidente con evidencia.
