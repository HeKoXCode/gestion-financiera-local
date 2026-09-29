# Gestión Financiera v1.6 — Cobranza ampliada

## Estado del documento

Este README registra el alcance, las decisiones y la validación de la versión
`1.6.2`. Las seis fases fueron implementadas sobre una copia independiente y la
versión anterior quedó preservada.

La base de partida fue v1.5.4. El resultado conserva sus datos y funciones,
elimina la nomenclatura fechada del nombre actual y amplía Cobranza sin sumar
usuarios, permisos ni dependencias de Internet.

## Decisiones ya cerradas

- `Pausar recargo` detiene únicamente los cargos diarios futuros. La deuda, los
  recargos ya generados y los días reales de atraso siguen visibles.
- La pausa corresponde a una venta, no al cliente completo, porque una persona
  puede tener varias compras con acuerdos diferentes.
- `Diaria` significa cada día de cobranza habilitado en Configuración; no todos
  los días calendario.
- Guardar una planilla establece al cobrador como habitual de esos clientes
  para la próxima cobranza. La persona siempre puede confirmar o cambiar la
  asignación antes de imprimir.
- El distintivo breve en la lista será `Cobrador: Esteban`. La explicación de
  que se trata del cobrador habitual quedará en la ayuda de la pantalla, sin
  recargar cada fila.
- El selector desplegable fue retirado después de comprobar que las tarjetas
  permiten crear, seleccionar, cambiar y archivar cobradores con las mismas
  validaciones del servidor.

## Objetivos

1. Permitir pausar y reactivar el recargo diario de una venta sin ocultar la
   deuda ni el atraso.
2. Incorporar la frecuencia de cobro diaria junto con semanal, cada dos semanas
   y mensual.
3. Recordar el cobrador habitual de cada cliente para las próximas cobranzas.
4. Completar el flujo por tarjetas y eliminar el selector desplegable de
   cobrador.

## Reglas que deben conservarse

- Las cuotas, recargos, pagos y anulaciones continúan siendo movimientos
  auditables. No se reemplazan por un saldo escrito manualmente.
- Pausar el recargo no borra cuotas, recargos ya generados ni días de atraso.
- Un cliente puede integrar una sola planilla por fecha, aunque tenga varias
  ventas pendientes.
- El cobrador habitual es una preferencia para el próximo recorrido. El pago
  histórico siempre conserva el cobrador que realmente realizó ese cobro.
- Archivar un cobrador nunca elimina sus planillas, visitas ni pagos anteriores.
- Toda migración debe funcionar sobre una copia de la base real y conservar las
  carpetas `data`, `backups`, `exports`, `media` y `storage` al actualizar.

## Fase 0 — Preparación y aceptación · completada

### Acciones

1. Crear un backup ZIP verificable de la base antes de modificar modelos.
2. Trabajar con una base aislada generada por `seed_demo_data`, con al menos 50
   clientes, 70 ventas y 5 cobradores.
3. Registrar por escrito los escenarios de aceptación de las cuatro mejoras.
4. Ejecutar la suite actual para disponer de una línea de base sin fallos.
5. Crear una versión nueva; no reutilizar un ZIP ya entregado.

### Criterio de salida

- Base ficticia disponible y base real sin tocar.
- Suite anterior aprobada.
- Reglas de fechas y recargos confirmadas antes de crear migraciones.

## Fase 1 — Selección de cobrador únicamente mediante tarjetas · completada

### Flujo final

1. La persona crea un cobrador.
2. Aparece inmediatamente una tarjeta con su nombre y queda seleccionada.
3. La tarjeta muestra información breve:
   - clientes habituales;
   - planillas realizadas;
   - clientes visitados;
   - total cobrado histórico.
4. Al seleccionar la tarjeta se habilita la lista de clientes.
5. Se eligen clientes y se guarda la planilla.

### Cambios técnicos

- Quitar el `<select name="collector">` de `collection/routes.html`.
- Cada tarjeta debe apuntar a `?fecha=AAAA-MM-DD&cobrador=ID` y comportarse como
  una opción única accesible.
- Cuando hay una tarjeta seleccionada, enviar el cobrador mediante un campo
  oculto validado nuevamente en el servidor.
- Sin tarjeta seleccionada, mostrar “Elegí un cobrador para preparar su
  planilla” y mantener deshabilitado Guardar planilla.
- Mantener dos estados visuales:
  - `Sin planilla para este día`: botón `Elegir clientes`;
  - planilla existente: botones `Cambiar clientes` e `Imprimir planilla`.
- Crear el cobrador no debe crear un `CollectionRoute` vacío. El recorrido nace
  recién al guardar al menos un cliente.
- La baja rápida sigue enviando el cobrador al Archivo seguro con dos
  confirmaciones.

### Pruebas

- Alta rápida, selección automática y foco en la lista de clientes.
- Intento de enviar un ID archivado o inexistente.
- Cambio entre tarjetas sin mezclar selecciones.
- Escritorio, tablet y celular sin desbordes.
- Navegación por teclado, foco visible y área táctil mínima de 44 px.

## Fase 2 — Cobrador habitual para la próxima cobranza · completada

### Modelo recomendado

Crear `CustomerCollectorLink` con:

- `customer`;
- `collector`;
- `started_at`;
- `ended_at`, opcional;
- `source_route`, opcional;
- motivo del cambio.

Debe existir un solo vínculo activo por cliente. El modelo con fecha de inicio y
fin conserva la historia cuando el cliente cambia de cobrador.

### Funcionamiento

- Al guardar una planilla, cada cliente elegido queda vinculado a ese cobrador
  como habitual.
- En la siguiente fecha de cobro, al seleccionar la tarjeta del cobrador, sus
  clientes habituales aparecen primero y preseleccionados.
- La persona confirma la planilla antes de crear el recorrido del día.
- La fila muestra un distintivo pequeño: `Cobrador: Esteban`.
- Si otro cobrador toma al cliente, el servicio cierra el vínculo anterior y
  crea uno nuevo dentro de una transacción.
- Si se archiva un cobrador, sus clientes quedan marcados `Reasignar cobrador`;
  nunca deben asociarse automáticamente a una persona archivada.
- Los pagos y visitas ya registrados conservan su cobrador histórico.

### Pruebas

- Primera asignación, repetición en la fecha siguiente y cambio de cobrador.
- Cliente con varias ventas: un solo vínculo y una sola visita por fecha.
- Cobrador archivado y posterior reasignación.
- Edición de planilla antes y después de registrar pagos o visitas.
- Reportes históricos sin modificaciones retroactivas.

## Fase 3 — Frecuencia de cobro diaria · completada

### Regla propuesta

`Diaria` significa **cada día de cobranza habilitado en Configuración**. Si el
negocio trabaja de lunes a sábado, no se crea una cuota el domingo. Esta regla
evita que el sistema programe visitas en días que el cobrador no trabaja.

### Cambios técnicos

- Agregar `DAILY = "daily", "Diaria"` a las frecuencias de `Sale`.
- Incluirla en Configuración y en el formulario de venta.
- Extender el generador de cuotas para avanzar al siguiente día habilitado.
- Mantener la misma regla para fecha de entrega y primer cobro.
- Mostrar ejemplos junto al campo: `Diaria: cada día de cobranza habilitado`.
- Revisar importación/exportación CSV y snapshots del Archivo seguro.

### Casos obligatorios

- Inicio un lunes, viernes, sábado y domingo.
- Meses de 28, 29, 30 y 31 días.
- Cambio de año.
- Días habilitados modificados después de crear la venta: las cuotas existentes
  no cambian; la configuración nueva se aplica solo a ventas nuevas.
- Pago adelantado y pago de una fecha anterior.

## Fase 4 — Pausar y reactivar el recargo diario · completada

### Alcance recomendado

La pausa se aplica **por venta**, porque un cliente puede tener varias compras y
solo una de ellas podría recibir la excepción.

Crear `LateFeePausePeriod` con:

- `sale`;
- `paused_from`;
- `resumed_at`, opcional;
- `reason`;
- fechas de creación y modificación.

Solo puede existir una pausa abierta por venta.

### Reglas financieras

- Los días de atraso continúan aumentando y se siguen mostrando.
- Las cuotas vencidas y los recargos anteriores permanecen pendientes.
- Mientras la pausa está activa, `generate_missing_late_fees` no crea nuevos
  recargos para esa venta.
- El día D produce, si corresponde, el recargo fechado en D+1. Por eso, pausar
  en D impide el recargo de D+1, pero nunca borra el de D ni los anteriores.
- Reactivar en D vuelve a habilitar el posible recargo de D+1. Los días que
  estuvieron pausados no se cobran retroactivamente.
- Pausar y reactivar deben ser operaciones idempotentes y transaccionales.
- No se permite borrar períodos de pausa desde la interfaz. Quedan como
  historial financiero.

### Interfaz sin saturar la fila

- Mantener las acciones principales `Registrar pago`, `No pagó` y `Otro`.
- Agregar una acción compacta `Pausar recargo` dentro del grupo secundario de
  acciones, con confirmación y motivo obligatorio.
- Cuando está pausado, reemplazarla por `Reactivar recargo`.
- Mostrar una sola insignia discreta junto al atraso:
  `Recargo pausado desde 17/09/2026`.
- No repetir la explicación completa en cada fila. Abrir el detalle mediante un
  ícono de información o texto de ayuda.
- En la planilla impresa mostrar únicamente `Recargo pausado`, debajo de los
  días de atraso.

### Pruebas financieras obligatorias

- Pausa antes y después de generar el recargo del día.
- Reactivación y generación al día siguiente.
- Varios períodos de pausa en la misma venta.
- Cuotas múltiples vencidas bajo la regla de un recargo diario por venta.
- Pagos parciales, adelantados y retroactivos durante la pausa.
- Venta finalizada o cancelada.
- Ejecución repetida del generador sin cargos duplicados.
- Fechas futuras o anteriores manipuladas desde el formulario.

## Fase 5 — Integración, reportes y exportación · completada

- Añadir el estado de pausa y el cobrador habitual a los detalles del cliente,
  sin exponer notas internas en el PDF que se comparte con el comprador.
- Incorporar los nuevos modelos a la exportación CSV y al respaldo completo.
- Conservar pausas y vínculos históricos en Archivo seguro.
- Revisar Inicio, Semana y Reportes para evitar dobles conteos.
- En reportes de cobradores utilizar asignaciones y pagos reales, no el vínculo
  habitual, que solo sirve para planificar.

## Fase 6 — QA y entrega portable · completada

1. Ejecutar `ruff`, `manage.py check` y control de migraciones pendientes.
2. Ejecutar toda la suite con cobertura mínima del 85 %.
3. Probar con datos ficticios:
   - 50 clientes;
   - 70 ventas;
   - ventas diarias, semanales, quincenales y mensuales;
   - pausas abiertas, cerradas y repetidas;
   - cambios y archivo de cobradores.
4. Verificar visualmente 1366×768, 768×1024 y 360×800.
5. Probar impresión A4 con filas normales y con recargo pausado.
6. Construir el portable y ejecutar el smoke test aislado.
7. Generar el ZIP completo y el ZIP de actualización.
8. Confirmar que el ZIP de actualización no incluya `data`, `backups`,
   `exports`, `media` ni `storage`.
9. Calcular SHA-256, auditar con Microsoft Defender y mover la versión anterior
   a `portable/anteriores`.

## Orden recomendado de implementación

1. Flujo exclusivo por tarjetas.
2. Cobrador habitual y reasignación segura.
3. Frecuencia diaria.
4. Pausa y reactivación del recargo.
5. Reportes, exportación y Archivo seguro.
6. QA integral y paquete portable.

El recargo se deja para una fase propia porque modifica cálculo financiero. No
debe mezclarse con una mejora visual ni liberarse sin pruebas de fechas,
idempotencia y pagos parciales.

## Resultado de la implementación

- Migración `0014_v16_collection_workflow` creada y validada sobre bases nuevas
  y existentes.
- Al actualizar una base 1.5, la migración toma la última planilla válida de
  cada cliente y la convierte en su cobrador habitual inicial. No se recuperan
  cobradores archivados.
- Selección por tarjetas, cobrador habitual, frecuencia diaria y pausas
  financieras integrados en servicios, pantallas, impresión y exportación.
- La pausa conserva el atraso, el capital y todo recargo anterior.
- El PDF compartido con el comprador no expone motivos internos de pausa ni
  decisiones de planificación de cobradores.
- Suite funcional: 307 pruebas aprobadas y 7 pruebas de préstamos omitidas por
  no pertenecer a esta línea del producto.
- Cobertura total: 86 %, por encima del mínimo obligatorio de 85 %.

## Evidencia final de QA

### Controles automáticos

- Ruff: sin observaciones.
- Django `check`: sin errores.
- Migraciones: sin cambios pendientes.
- Pytest: 307 aprobadas y 7 omitidas por corresponder al módulo de préstamos
  que no forma parte de esta versión.
- Cobertura combinada de líneas y ramas: 86 %.

### Actualización desde la versión anterior

Se migró una copia aislada de una base 1.5 con 50 clientes, 70 ventas, 6
cobradores, 109 pagos y 116 planillas. Después de aplicar
`0014_v16_collection_workflow`, todos esos conteos permanecieron iguales y se
recuperaron 43 vínculos de cobrador habitual a partir de la última planilla
válida de cada cliente. La base 1.5 de origen no se modificó.

### QA visual y de impresión

- Parche 1.6.2: `Guardar e imprimir` confirma la selección actual antes de
  abrir la impresión. Si la planilla ya existe, la actualiza sin crear un
  recorrido duplicado. Los botones fueron revisados en escritorio y celular.
- Parche 1.6.1: seis tarjetas de cobradores, incluido un nombre largo, se
  distribuyen en tres columnas en escritorio, dos en tablet y una en celular,
  sin recortes ni desplazamiento horizontal.
- Escritorio 1366×768: Cobranza, planillas, historial y detalle de cobradores,
  venta diaria, pausas e impresión sin desbordes.
- Tablet 768×1024: formulario de venta y preparación de planillas fluidos y
  sin desplazamiento horizontal.
- Celular 360×800: Cobranza, panel de pausa, tarjetas, selección de clientes,
  alta rápida e historial de cobradores legibles y sin recortes.
- Planilla diaria: 35 cobros distribuidos en 4 hojas, con un máximo de 10 por
  hoja y la marca visible de interés pausado.
- Planillas por cobrador: 5 hojas separadas, cada una identificada con su
  cobrador.
- Consola del navegador: sin errores ni advertencias durante el recorrido.

### Artefactos portables auditados

- Instalación completa:
  `portable/GestionFinanciera-v1.6.2-windows-x64.zip`, 58.891.739 bytes,
  SHA-256
  `454F1ACAAA1F7685EB2D8F369EE15BB87A2E3A1CB1CE42EC5DCB68E693F856A1`.
- Actualización que preserva datos:
  `portable/GestionFinanciera-actualizacion-1.6.2.zip`, 58.894.371 bytes,
  SHA-256
  `D312D8EBE4F4924D22B921A5CF74D9F37FDD9B0B1393E441F6921C1C71AEC30C`.
- Ambos ZIP aprobaron checksum, rutas seguras, ausencia de archivos sensibles,
  smoke test aislado y Microsoft Defender sin detecciones.
- La carpeta portable compilada contiene `VERSION.txt` con `1.6.2`; sus
  carpetas de usuario están vacías.
- Los ejecutables no poseen firma Authenticode porque no hay un certificado de
  firma de código disponible. La integridad se comprueba con
  `portable/SHA256SUMS.txt` y los reportes `release-audit-v1.6.2.json` y
  `release-audit-update-v1.6.2.json`.
- Las entregas `1.6.0` y `1.6.1` permanecen completas en
  `portable/anteriores` como respaldo histórico.

## Definición de terminado

La etapa se considera finalizada cuando:

- no existe selector desplegable de cobrador;
- crear o tocar una tarjeta basta para preparar su planilla;
- el cobrador habitual se conserva y puede reasignarse con historia;
- las ventas diarias generan fechas válidas según los días habilitados;
- una venta pausada mantiene deuda y atraso, pero no genera recargo nuevo;
- reactivar no cobra retroactivamente el período pausado;
- pantalla, impresión, exportación, respaldo y restauración coinciden;
- la base real puede actualizarse sin perder datos.

Todos estos puntos están implementados en el código de v1.6. La entrega debe
hacerse mediante el ZIP completo en una instalación nueva o mediante el ZIP de
actualización cuando se deban conservar `data`, `backups`, `exports`, `media` y
`storage` de una instalación existente.
