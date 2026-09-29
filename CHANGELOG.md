# Changelog

Los cambios relevantes de Gestión Financiera se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto utiliza [versionado semántico](https://semver.org/lang/es/).

## [Unreleased]

### Corregido

- Se restauraron los estilos del acceso multiusuario y de Analítica que se
  habían perdido durante la unificación 1.8.0; los KPI, el aging, las cohortes
  y la conciliación vuelven a conservar su grilla y jerarquía visual.

### Documentación

- Se renovaron las cinco capturas de producto y el recorrido animado con una
  base demo ficticia y aislada de la versión integrada.

## [1.8.0] - 2026-09-29

### Agregado

- Perfil multiusuario opcional con autenticación, roles de administrador y
  cobrador, auditoría de operaciones y despliegue PostgreSQL detrás de HTTPS.
- Panel analítico con cartera, mora, recuperación, aging, cohortes y
  conciliaciones; exportación seudonimizada preparada para Power BI.
- Integración de las funciones finales de la edición local: préstamos,
  cobradores, recorridos, pagos adelantados, Archivo seguro y correcciones
  versionadas.
- Migración de unión que admite tanto el historial publicado en GitHub como el
  historial de las ediciones portables 1.7.x.

### Cambiado

- El producto queda publicado como software gratuito y completo bajo MIT. La
  demostración utiliza datos ficticios aislados, sin limitar clientes ni
  esconder una licencia evitable en el equipo local.
- La interfaz, el lanzador y el acceso móvil comparten la identidad azul
  petróleo y cian de la edición 1.7.2.
- El sistema local conserva SQLite y serializa escrituras; el perfil
  multiusuario utiliza PostgreSQL, HTTPS y backups verificados.

### Verificado

- Suite funcional integrada, cobertura, Ruff, chequeos de Django y control de
  migraciones.
- Actualización ensayada desde las dos historias de base de datos y creación
  desde cero en un entorno aislado.
- Portable, demostración aislada, respaldo/restauración, contenido sensible y
  Microsoft Defender antes de publicar los artefactos.

## [1.7.2] - 2026-09-28

### Cambiado

- La ventana inicial adopta la misma identidad azul petróleo y cian que la
  aplicación web, incluyendo encabezado, botones, estados, fondos y firma.
- El acceso desde celular y su código QR usan la nueva paleta para mantener una
  experiencia visual continua desde la apertura hasta el uso cotidiano.
- El logotipo alternativo dejó el acento dorado y ahora utiliza un tratamiento
  azul claro coherente con el resto del sistema.

### Verificado

- Paleta del launcher y del QR cubierta por una prueba automática de regresión.
- Suite automática, portable aislado, contenido sensible y Microsoft Defender.

## [1.7.1] - 2026-09-28

### Cambiado

- La identidad general pasa del verde azulado a la paleta azul/cian de la
  edición original con préstamos, conservando contraste y legibilidad.
- Los préstamos usan un azul índigo propio en tarjetas, distintivos, listados,
  detalle, vista previa y reportes para diferenciarlos del resto del sistema.
- Paneles, encabezados, campos, botones y estados incorporan mayor profundidad
  visual, focos más claros y transiciones moderadas.
- La selección de clientes por cobrador alinea nombre, distintivos, detalle e
  importe en columnas estables; en celular vuelve a una sola columna.

### Corregido

- El total de la vista previa de un préstamo mantiene texto oscuro y legible
  sobre su nuevo fondo claro.

### Verificado

- QA visual con datos ficticios en detalle de préstamo, alta, operaciones,
  cobranza y preparación de planillas en escritorio y celular.
- Suite completa, chequeos de Django, migraciones y paquete portable aislado.

## [1.7.0] - 2026-09-25

### Agregado

- Préstamos de dinero integrados al mismo circuito de clientes, cuotas, pagos,
  cobranza, cobradores, reportes, exportaciones y Archivo seguro.
- Registro del capital entregado, medio de entrega, porcentaje de interés total
  y total final a devolver, con cálculo dinámico y posibilidad de acordar un
  total personalizado.
- Distintivos visuales propios para préstamos en el alta, listados, historial
  del cliente, detalle, cobranza y reportes.
- Resumen de préstamos en Reportes: cantidad, capital prestado, total a devolver
  y saldo pendiente.
- Pruebas de regresión específicas para creación, calendario diario, edición
  protegida e integración con cobranza y recorridos.

### Cambiado

- El menú y las pantallas comunes usan `Operaciones` para abarcar ventas y
  préstamos sin confundir al usuario.
- La selección de clientes por cobrador adapta la altura de cada fila a su
  contenido; nombres, distintivos, operaciones e importes ya no se pisan.
- Mensajes y validaciones compartidos hablan de `operación` cuando pueden
  corresponder tanto a una venta como a un préstamo.

### Verificado

- Suite completa, análisis estático, chequeos de Django y control de migraciones.
- QA visual con datos ficticios en escritorio y celular, incluido cálculo de
  préstamos, listados, detalle, historial, reportes y recorridos de cobradores.

## [1.6.2] - 2026-09-17

### Agregado

- La preparación o edición de una planilla ofrece `Guardar e imprimir`: valida
  y guarda la selección actual antes de abrir la vista de impresión.

### Cambiado

- El botón general ahora dice `Imprimir planillas guardadas`, para aclarar que
  no incluye selecciones diarias que todavía no fueron confirmadas.
- El usuario puede modificar una planilla del mismo día y volver a usar
  `Guardar e imprimir`; se actualiza el recorrido existente sin duplicarlo.

### Verificado

- Se probaron creación, actualización, redirección a impresión y ausencia de
  duplicados mediante pruebas automatizadas.
- Los botones fueron revisados en escritorio y celular con datos ficticios,
  sin recortes, desbordes ni errores de navegador.

## [1.6.1] - 2026-09-17

### Cambiado

- Las tarjetas de cobradores ahora aprovechan mejor el ancho disponible: se
  muestran tres por fila en escritorio, dos en tablet y una en celular.

### Corregido

- El contador de clientes seleccionados ya no genera un error de JavaScript
  cuando todavía no se eligió un cobrador o no hay clientes disponibles.

### Verificado

- Se revisó la pantalla con seis cobradores, incluido un nombre largo, en
  1366×768, 768×1024 y 360×800, sin recortes ni desplazamiento horizontal.
- La consola del navegador quedó sin errores ni advertencias en los estados
  con y sin cobrador seleccionado.

## [1.6.0] - 2026-09-17

### Agregado

- Frecuencia diaria: crea una cuota por cada día de cobranza habilitado en
  Configuración y salta automáticamente los días no laborables.
- Pausa y reactivación del recargo diario por venta, con motivo obligatorio e
  historial inalterable. Pausar el día D impide el recargo de D+1; reactivar el
  día D habilita nuevamente el posible recargo de D+1.
- Cobrador habitual por cliente, con historial de reasignaciones y selección
  automática —siempre editable— al preparar la próxima planilla.
- Nuevos CSV `pausas_recargo_diario.csv` y `cobradores_habituales.csv`, además
  de estos registros en las copias históricas del Archivo seguro.
- Pruebas específicas de la etapa v1.6 para fechas, idempotencia, migración,
  auditoría, asignaciones, exportación e interfaz.

### Cambiado

- Preparar planillas usa exclusivamente tarjetas de cobrador. Se eliminó el
  selector desplegable redundante sin quitar la validación del servidor.
- La lista de Cobranza muestra de forma compacta si el recargo está pausado y
  quién es el cobrador habitual, sin ocultar deuda ni días de atraso.
- Las planillas impresas indican `Interés diario pausado` sin exponer el motivo
  interno al cliente.
- La versión pública pasa a la nomenclatura semántica simple `1.6.0`; los
  nombres anteriores con fecha se conservan únicamente como registro histórico.

### Corregido

- Las estadísticas de tarjetas de cobradores se precargan en bloque para que la
  cantidad de consultas no crezca por cada tarjeta agregada.
- Las cuotas diarias conservan sus fechas originales aunque luego cambien los
  días habilitados en Configuración.
- La actualización recupera como cobrador habitual la asignación válida más
  reciente de cada cliente en las planillas anteriores.
- La tabla de cobradores muestra todas sus columnas y acciones sin desplazarse
  horizontalmente en escritorio.
- La planilla diaria diferencia la cantidad de clientes de la cantidad de
  cobros cuando una persona posee más de una venta pendiente.

### Verificado

- 307 pruebas aprobadas y 7 omitidas por pertenecer al módulo de préstamos no
  incluido en esta versión.
- Ruff, chequeos de Django, migraciones, cobertura, QA visual y auditoría del
  portable se registran en el README de v1.6.

## [1.5.4-edicion01ago] - 2026-09-17

### Agregado

- Los cobradores sin recorrido aparecen como tarjetas “Sin planilla para este
  día”, sin crear registros vacíos ni alterar sus días trabajados.
- Al crear un cobrador desde Preparar planillas, su tarjeta aparece de
  inmediato, queda seleccionada y la página lleva directamente a elegir
  clientes.
- La pantalla aclara que la selección es por cliente y muestra juntas todas sus
  ventas pendientes para mantener una sola visita por fecha.
- Plan documentado para la próxima etapa: recargo pausado, frecuencia diaria,
  cobrador habitual y selección exclusiva mediante tarjetas.

### Corregido

- El buscador de clientes y productos ahora oculta realmente las filas que no
  coinciden; una regla visual anterior anulaba el atributo `hidden`.
- Los nombres de varias ventas ya no se cortan con puntos suspensivos y pueden
  ocupar las líneas necesarias dentro de la fila.

### Verificado

- Flujo completo con 50 clientes, 70 ventas, 5 cobradores ficticios y un sexto
  cobrador creado durante el QA.
- Alta, selección automática, búsqueda por cliente y producto, guardado de la
  planilla y conversión de la tarjeta al estado imprimible.
- Matriz visual en escritorio, tablet y celular sin desbordes horizontales.
- 291 pruebas aprobadas, 7 omitidas por corresponder a préstamos no incluidos
  en esta edición y cobertura total del 86 %.

## [1.5.3-edicion01ago] - 2026-09-16

### Agregado

- Cada tarjeta de cobrador en Preparar planillas incluye una baja rápida con
  dos confirmaciones; el cobrador pasa al Archivo seguro y conserva todas sus
  planillas, visitas y cobros históricos.
- Navegación directa por Día anterior y Día siguiente, además del selector de
  fecha, para consultar y volver a imprimir planillas anteriores.

### Mejorado

- Los clientes asignados a otra persona se distinguen con un borde y fondo
  suaves, y la leyenda roja “Asignado a cobrador ...”, sin perder legibilidad.
- Las acciones ahora usan nombres directos: “Cambiar clientes” e “Imprimir
  planilla”.
- El historial diario de cada cobrador queda centrado, conserva márgenes y no
  desborda en escritorio, tablet ni celular.
- El botón de baja alcanza un área táctil de 44 px y la navegación entre días
  mantiene una distribución simétrica en pantallas angostas.

### Verificado

- Pruebas funcionales para la baja segura, la conservación de recorridos y el
  rechazo de redirecciones externas.
- Matriz visual en 1366×768, 768×1024 y 360×800 sin desbordes horizontales.

## [1.5.2-edicion01ago] - 2026-09-16

### Mejorado

- La navegación marca de forma accesible la sección actual y la desplaza al
  centro de la barra en pantallas angostas, para que siempre quede visible.
- Cobradores y movimientos se adaptan como tarjetas legibles en tablet y
  celular; sus acciones ya no quedan fuera de la pantalla.
- Las planillas por cobrador usan palabras más directas y consistentes:
  “planilla”, “visitas asignadas”, “clientes distintos” y “mostrar fecha”.
- Los botones compactos alcanzan un tamaño táctil cómodo en celular.
- La sección de pagos y visitas de una venta usa una sola columna cuando el
  espacio disponible no permite mostrar ambas sin recortes.

### Agregado

- Plan profesional de QA para revisar datos, cálculos, flujos completos,
  claridad del lenguaje, accesibilidad y adaptación a distintos tamaños.
- Pruebas automáticas para la navegación activa, las tablas de cobradores, la
  terminología de acciones y los límites visuales de las planillas.

### Verificado

- Matriz visual en 1366×768, 768×1024 y 360×800 sin desbordes de página.
- 286 pruebas aprobadas y cobertura total del 86 %.

## [1.5.1-edicion01ago] - 2026-09-16

### Agregado

- Baja protegida de cobradores: dejan de aparecer en recorridos nuevos y pasan
  a Configuración → Archivo seguro, conservando recorridos, clientes y cobros.
- Tres utilitarios portables para cargar datos ficticios, limpiar la base de
  prueba y recuperar automáticamente la base original protegida.
- Ingesta demostrativa de 50 clientes, 70 ventas y 5 cobradores con actividad
  histórica atribuida.

### Corregido

- El panel “Agregar cobrador” ahora tiene relleno, ancho seguro y controles que
  no se recortan.
- Las estadísticas de visitas cuentan una persona una sola vez por fecha,
  aunque tenga varias ventas.

## [1.5.0-edicion01ago] - 2026-09-16

### Agregado

- Cobradores simples identificados por nombre, sin usuarios, contraseñas ni
  permisos adicionales.
- Preparador de recorridos desde Cobranza, con buscador, selección múltiple de
  clientes y alta rápida de cobradores.
- Una planilla A4 independiente por cobrador, con hasta 10 clientes por hoja y
  opción de imprimir un recorrido o todos los recorridos del día.
- Registro histórico por cobrador: fechas con recorridos, asignaciones,
  clientes diferentes, importes previstos, dinero cobrado y frecuencia por
  cliente.
- Nuevos CSV para cobradores, recorridos y asignaciones, junto con las
  relaciones del cobrador en pagos y visitas.

### Cambiado

- La planilla por cobrador agrupa por persona: si un cliente tiene más de una
  venta pendiente, ocupa una sola entrada con el total combinado.
- Los pagos y resultados de visita se atribuyen automáticamente al cobrador
  asignado para ese cliente y esa fecha, sin agregar pasos al cobro habitual.
- Inicio y Semana muestran un resumen discreto de cobradores y clientes
  asignados, sin convertirlos en el indicador principal.

### Protegido

- Un cliente solo puede pertenecer a un recorrido por fecha.
- Una asignación con pagos o visitas ya registrados no puede quitarse ni
  transferirse a otro cobrador.
- Cada asignación conserva una copia del domicilio, operaciones e importe
  esperado al momento de preparar la planilla.

## [1.3.2-edicion01ago] - 2026-08-26

### Corregido

- Los resúmenes de cuenta para pantalla, impresión, PDF y WhatsApp ya no
  incluyen ventas canceladas, sus cuotas, pagos, visitas ni movimientos.
- Los totales abonados y pendientes del cliente se calculan solamente con sus
  operaciones vigentes o finalizadas.
- Los conteos de ventas de Clientes y Productos, Cobranza, Semana, Inicio y
  Reportes excluyen las operaciones canceladas incluso al consultar una fecha
  anterior a la cancelación.
- El detalle protegido de una venta cancelada vuelve ahora a Configuración →
  Archivo seguro, único apartado habitual donde puede consultarse.

## [1.3.1-edicion01ago] - 2026-08-25

### Agregado

- Flujo separado “Registrar pago adelantado” dentro de Cobranza, con buscador
  por cliente, DNI o producto.
- Acceso directo desde Cliente → Venta → calendario de cuotas para adelantar la
  próxima cuota semanal, quincenal o mensual.
- Identificación permanente de los adelantos en historiales, resúmenes, PDF,
  Archivo seguro y exportación CSV.

### Reglas protegidas

- El adelanto se registra con la fecha real de hoy y se aplica desde la cuota
  futura pendiente más cercana.
- No desplaza ningún vencimiento ni otorga días de gracia.
- Un adelanto parcial conserva el saldo y la fecha original de esa cuota.
- Un pago normal nunca consume cuotas futuras; solo el flujo explícito de
  adelanto puede hacerlo.
- Si existe deuda vencida o del día, primero debe registrarse el pago normal.

## [1.3.0-edicion01ago] - 2026-08-24

### Added

- Trazabilidad de importes de recargo dejados sin efecto, con motivo y fecha,
  para actualizar bases v1.2.2 sin borrar su historial.
- Pruebas de la regla combinada: cuotas 1 y 2 por $20.000, atrasos de 10 y 3
  días, recargo diario de $5.000 y total exigible de $90.000.

### Changed

- Cobranza, reportes e impresión suman el capital de todas las cuotas vencidas.
- El recargo se calcula una vez por día para toda la venta desde la cuota
  impaga más antigua, nunca una vez por cada cuota atrasada.
- El historial mantiene los días individuales de atraso de cada cuota sin
  utilizarlos como sumas adicionales.
- Los pagos pueden cubrir varias cuotas vencidas y conservan la prioridad de
  recargo acumulado antes del capital.
- Configuración conserva el importe diario, domingos y continuidad después de
  pagos parciales.

### Fixed

- Las cuotas 2, 3 y siguientes aumentan el capital vencido, pero ya no duplican
  el recargo de una fecha que la venta ya tenía contabilizada.
- Los recargos superpuestos de una base anterior dejan de integrar la deuda sin
  eliminar registros ni pagos históricos.

## [1.2.2-edicion01ago] - 2026-08-24

### Changed

- La planilla diaria utiliza un diseño compacto de hasta 10 clientes por hoja
  A4. Conserva cliente, domicilio, producto, deuda, recargos, atraso, firma y
  observaciones; 50 clientes ahora ocupan 5 hojas en lugar de 13.

## [1.2.1-edicion01ago] - 2026-08-24

### Added

- Confirmación clara antes de registrar desde Cobranza un pago correspondiente
  a un día anterior.
- La fecha elegida en Cobranza se conserva y queda protegida durante la carga
  del pago.

### Changed

- Los recargos de un pago anterior se calculan sólo hasta la fecha real en que
  fue recibido.
- La planilla diaria se divide expresamente en hojas A4 de hasta 4 clientes,
  repitiendo encabezado, total general, número de hoja y pie en cada página.

### Fixed

- Se eliminan recargos posteriores que hubieran sido generados antes de cargar
  un pago retroactivo que los detiene.
- Se impide insertar un pago anterior delante de otro pago de cuotas ya
  registrado, evitando alterar silenciosamente el orden contable.
- El campo de fecha HTML conserva correctamente el formato `AAAA-MM-DD`.

## [1.2.0-edicion01ago] - 2026-08-23

### Added

- Historial inalterable de cada corrección de datos personales y domicilio de
  clientes, con motivo, fecha y vista detallada en el Archivo seguro.
- Enlaces directos a cada venta activa que impide borrar un cliente.
- Corrección excepcional, avanzada y de un solo uso para ventas que ya tienen
  pagos o visitas, con doble confirmación escrita.
- Exportación CSV de las versiones anteriores de clientes.

### Changed

- El Archivo seguro ahora permite abrir en profundidad clientes borrados,
  ventas canceladas, versiones anteriores de clientes y versiones anteriores
  de ventas, incluyendo cuotas, recargos, pagos, aplicaciones y visitas.
- Una corrección excepcional conserva los pagos originales y reconstruye su
  aplicación al nuevo plan dentro de una sola transacción. Si un pago o visita
  no es compatible, se revierte la operación completa.
- Los envíos repetidos de una misma corrección ya no consumen otra edición.
- Las correcciones sin cambios reales son rechazadas.

### Security

- Las ventas canceladas y los historiales de clientes borrados ya no permiten
  anular pagos ni alterar movimientos por una URL directa.
- La autorización excepcional se desactiva automáticamente después de una
  corrección exitosa y exige `HABILITAR` y luego `RECALCULAR`.

## [1.1.0-edicion01ago] - 2026-08-23

### Added

- Archivo seguro dentro de Configuración para consultar clientes borrados,
  ventas canceladas y versiones anteriores de ventas.
- Borrado protegido de clientes con motivo obligatorio, sin eliminación física
  de sus datos ni de su historial.
- Corrección de ventas activas hasta dos veces, guardando antes de cada cambio
  una copia completa e inalterable de las condiciones, cuotas y movimientos.
- Exportación CSV del historial de versiones anteriores.

### Changed

- Las ventas canceladas dejaron la lista diaria de Ventas y se centralizaron en
  el Archivo seguro.
- Una venta con pagos de cuotas o visitas de cobranza ya registradas no puede
  editarse; debe cancelarse y cargarse correctamente para proteger el historial.
- Un cliente con una venta activa no puede borrarse hasta finalizarla o
  cancelarla.

### Security

- Los clientes borrados, las ventas canceladas y las versiones anteriores son
  registros de solo lectura y no disponen de acciones de edición o eliminación.

## [1.0.0] - 2026-08-13

### Added

- Flujo integrado de préstamos con capital, interés total y medio de entrega.
- Estado de cuenta del cliente en PDF, impresión y opción de compartir.
- Acceso temporal desde celular mediante token de sesión y red local.
- Paquete de actualización que conserva datos, respaldos, exportaciones y archivos del usuario.
- Evidencia visual generada con una base completamente ficticia.
- Validación continua de lint, Django, migraciones, pruebas y cobertura.
- ZIP portable versionado, checksum SHA-256 y auditoría desde extracción aislada.
- Workflow de prueba de release para tags y ejecuciones manuales.
- GIF reproducible del recorrido operación → cuotas/pagos → cobranza → reportes.

### Changed

- README preparado para publicación pública y distribución mediante GitHub Releases.
- Versión del proyecto alineada a `1.0.0`.
- Documentación histórica separada del plan vigente.
- Documentación de cierre GF-I1 a GF-I4 y modelo de datos simplificado.

### Security

- Bases, claves locales, respaldos, exportaciones, outputs y paquetes portables permanecen fuera de Git.
- El acceso móvil se mantiene deshabilitado por defecto y utiliza un token aleatorio por ejecución.
- El ZIP final se rechaza si contiene bases, claves, backups, exportaciones o rutas inseguras.
- La decisión de distribuir `v1.0.0` sin firma Authenticode queda explícita junto con la verificación por SHA-256 y Microsoft Defender.

[Unreleased]: https://github.com/HeKoXCode/gestion-financiera-local/compare/v1.8.0...HEAD
[1.8.0]: https://github.com/HeKoXCode/gestion-financiera-local/compare/v1.1.0...v1.8.0
[1.7.2]: https://github.com/HeKoXCode/gestion-financiera-local/compare/v1.7.1...v1.7.2
[1.7.1]: https://github.com/HeKoXCode/gestion-financiera-local/compare/v1.7.0...v1.7.1
[1.7.0]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.7.0
[1.6.2]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.6.2
[1.6.1]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.6.1
[1.6.0]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.6.0
[1.5.4-edicion01ago]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.5.4-edicion01ago
[1.5.3-edicion01ago]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.5.3-edicion01ago
[1.5.2-edicion01ago]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.5.2-edicion01ago
[1.5.1-edicion01ago]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.5.1-edicion01ago
[1.5.0-edicion01ago]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.5.0-edicion01ago
[1.3.2-edicion01ago]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.3.2-edicion01ago
[1.3.1-edicion01ago]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.3.1-edicion01ago
[1.3.0-edicion01ago]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.3.0-edicion01ago
[1.2.2-edicion01ago]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.2.2-edicion01ago
[1.2.1-edicion01ago]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.2.1-edicion01ago
[1.2.0-edicion01ago]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.2.0-edicion01ago
[1.1.0-edicion01ago]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.1.0-edicion01ago
[1.0.0]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.0.0
