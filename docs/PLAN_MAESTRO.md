# Plan maestro de desarrollo

> **Documento reemplazado para la implementación actual.** El alcance fue
> reducido a una aplicación local monousuario terminable en 2–3 días. El plan
> vigente es [PLAN_MVP_LOCAL.md](PLAN_MVP_LOCAL.md). Este documento se conserva
> solamente como referencia de una posible versión empresarial futura.

Versión: 1.0  
Estado: listo para iniciar la fase 0  
Proyecto: Sistema de Gestión de Ventas Financiadas y Cobranza  
Carpeta: `C:\Users\HeKoX\Downloads\GestionFinanciera`

## 1. Propósito de este documento

Este documento divide el proyecto completo en fases pequeñas, verificables y
ordenadas. Cada fase contiene:

- objetivo;
- decisiones necesarias;
- tareas técnicas;
- tareas del propietario del negocio;
- entregables;
- pruebas;
- criterio de aceptación;
- dependencias para avanzar.

No se considerará terminada una fase solamente porque exista una pantalla. Debe
funcionar con datos reales de ejemplo, tener pruebas y producir resultados
reconciliables.

## 2. Resultado final esperado

La versión 1 estará finalizada cuando un usuario autorizado pueda:

1. Ingresar de forma segura.
2. Crear y mantener clientes.
3. Crear productos.
4. Registrar una venta financiada.
5. Previsualizar y generar su cronograma de cuotas.
6. Consultar quién debe pagar en una fecha.
7. Ver capital, recargos, pagos y saldo sin cálculos manuales.
8. Registrar pagos totales o parciales sin duplicarlos.
9. Registrar una visita en la que el cliente no pagó.
10. Revertir un pago incorrecto dejando auditoría.
11. Consultar el historial completo de un cliente.
12. Consultar agenda diaria y atrasos.
13. Imprimir o descargar la planilla A4.
14. Consultar los reportes solicitados.
15. Configurar reglas operativas sin editar código.
16. Usar la interfaz desde computadora y celular.
17. Respaldar y restaurar la base de datos.
18. Trasladar el sistema a otra computadora o servidor.
19. Recuperar el servicio después de un fallo documentado.
20. Explicar cada total a partir de movimientos guardados.

La integración con WhatsApp será una ampliación posterior a la puesta en
producción de la versión 1. Está incluida en este plan, pero no bloqueará el
inicio de la cobranza.

## 3. Alcance

### 3.1 Alcance obligatorio de la versión 1

- Autenticación.
- Roles Administrador y Cobrador.
- Configuración del negocio.
- Clientes.
- Productos.
- Ventas financiadas.
- Frecuencias semanal y quincenal.
- Cronograma de cuotas.
- Cuotas futuras, del día y vencidas.
- Recargo diario.
- Pagos totales y parciales.
- Aplicación de pagos a la deuda.
- Reversión de pagos.
- Registro de intentos de cobranza.
- Dashboard.
- Agenda por fecha y día de semana.
- Historial del cliente.
- Reportes solicitados.
- PDF A4.
- Auditoría.
- Importación inicial controlada.
- Backups y restauración.
- Despliegue con HTTPS.
- Documentación y capacitación.

### 3.2 Ampliaciones posteriores

- Recordatorios automáticos por WhatsApp.
- Instalación como PWA.
- Trabajo sin conexión y sincronización posterior.
- Geolocalización y optimización de recorridos.
- Firma digital en pantalla.
- Integración bancaria.
- Facturación fiscal.
- Power BI.
- Aplicación móvil nativa.
- Inventario y control de stock.
- Múltiples empresas en la misma instalación.

### 3.3 Fuera de alcance de la versión 1

- Contabilidad de doble partida.
- Facturación electrónica de ARCA.
- Cálculo impositivo.
- Gestión de proveedores.
- Compra y reposición de mercadería.
- Caja y conciliación bancaria completa.
- Cobranza offline con sincronización automática.

Excluir estas funciones evita que el primer lanzamiento se convierta en un
ERP indefinido. Podrán añadirse mediante nuevas fases.

## 4. Forma de trabajo conjunto

Cada fase se desarrollará con este ciclo:

1. Revisar reglas y ejemplos.
2. Registrar decisiones en documentación.
3. Crear una rama de trabajo.
4. Implementar una porción funcional completa.
5. Crear migraciones si cambia la base.
6. Añadir pruebas automáticas.
7. Ejecutar las pruebas en PostgreSQL.
8. Probar manualmente en computadora y celular.
9. Mostrar el resultado con datos de demostración.
10. Corregir observaciones.
11. Actualizar documentación.
12. Cerrar la fase con un commit identificable.

### Responsabilidades de Codex

- Diseñar la solución técnica.
- Implementar código y migraciones.
- Crear pruebas.
- Ejecutar verificaciones.
- Mantener la documentación.
- Reportar supuestos, riesgos y resultados.
- No avanzar silenciosamente ante una regla financiera ambigua.

### Responsabilidades del propietario del proyecto

- Confirmar las reglas comerciales.
- Aportar ejemplos reales y casos excepcionales.
- Proporcionar nombre y logo del negocio.
- Probar los flujos como usuario.
- Validar cálculos y formatos impresos.
- Elegir el alojamiento final.
- Proporcionar credenciales externas cuando corresponda.
- Aprobar el paso de piloto a producción.

## 5. Decisiones técnicas aprobadas

| Área | Decisión |
| --- | --- |
| Arquitectura | Aplicación web monolítica |
| Backend | Python 3.12 y Django 5.2 LTS |
| Interfaz | Plantillas Django, Bootstrap y HTMX puntual |
| Base de datos | PostgreSQL 18.4 |
| Importes | Decimal exacto, nunca `float` |
| PDF | WeasyPrint dentro del contenedor |
| Desarrollo | Docker Compose |
| Producción | Contenedores Linux y PostgreSQL administrado o respaldado |
| Zona horaria | `America/Argentina/Buenos_Aires` |
| Idioma | Interfaz en español |
| Código | Nombres técnicos consistentes; textos visibles en español |
| API | No se crea una API pública en la versión 1 |
| Frontend SPA | No se usa React/Vue en la versión 1 |
| Tareas diarias | Comando idempotente programado |
| WhatsApp | Meta Cloud API en fase posterior |

## 6. Reglas de negocio que deben cerrarse en la fase 0

Estas decisiones son bloqueantes para el motor financiero. Se propone un valor
predeterminado para poder avanzar.

| Tema | Regla propuesta |
| --- | --- |
| Inicio del recargo | El día posterior al vencimiento |
| Días que generan recargo | Días calendario |
| Unidad del recargo | Por cuota vencida y por día |
| Pago parcial | El recargo continúa mientras quede saldo |
| Orden entre cuotas | Primero la cuota más antigua |
| Orden dentro de una cuota | Primero recargos; después capital |
| Cambio del recargo global | Afecta ventas nuevas, no contratos anteriores |
| Exceso de pago | Se rechaza en la versión 1 |
| Pago anticipado | Se permite solamente sobre cuotas ya generadas y seleccionadas |
| Cliente con varias ventas | Se muestra una línea por venta, agrupable por cliente |
| Cliente atrasado | Aparece todos los días hasta cancelar |
| Día habitual | Se deriva del primer vencimiento |
| No pagó | Registra intento; no agrega un cargo extra |
| Corrección de pago | Se revierte; nunca se elimina |
| Eliminación de cliente | Se archiva si tiene historia |
| Eliminación de producto | Se desactiva si fue utilizado |
| Redondeo | La última cuota absorbe diferencias de centavos |
| Hora de corte | Medianoche de Buenos Aires |
| Reportes | Usan fecha efectiva del pago, no fecha de carga |
| Recargo al pagar tarde | Se genera el correspondiente a ese día antes del pago |

### Decisiones adicionales que requieren ejemplo real

1. ¿Domingos y feriados generan recargo?
2. ¿El recargo tiene un máximo por cuota?
3. ¿Puede perdonarse un recargo? ¿Quién puede hacerlo?
4. ¿Una venta cancelada conserva deuda, la condona o exige devolución?
5. ¿Se aceptan pagos adelantados de cuotas futuras?
6. ¿Un pago general puede repartirse entre varias ventas?
7. ¿Qué ocurre si el monto financiado no coincide con cuotas por importe?
8. ¿Cuánto historial existe en los cuadernos?
9. ¿Se conoce cada pago anterior o solamente el saldo actual?
10. ¿El cobrador podrá registrar pagos desde su celular en la primera salida?

Toda respuesta se guardará en `docs/REGLAS_NEGOCIO.md`.

## 7. Definiciones funcionales

### 7.1 Indicadores

| Indicador | Definición |
| --- | --- |
| Clientes a cobrar | Clientes distintos con deuda exigible a la fecha |
| Monto esperado | Capital vencido pendiente más recargos acumulados |
| Clientes atrasados | Clientes con una cuota anterior a la fecha y saldo |
| Total adeudado | Capital pendiente futuro y vencido más cargos acumulados |
| Cobrado hoy | Pagos efectivos de hoy que no fueron revertidos |
| Clientes al día | Clientes con venta activa y sin deuda vencida |
| Total pendiente | Cargos vigentes menos pagos y créditos aplicados |
| Días de atraso | Días desde el vencimiento más antiguo aún abierto |

### 7.2 Estados

Cliente:

- `ACTIVE`: disponible para nuevas ventas.
- `ARCHIVED`: conserva historial, no aparece en altas comunes.

Producto:

- `ACTIVE`.
- `INACTIVE`.

Venta:

- `DRAFT`: todavía no genera deuda definitiva.
- `ACTIVE`: cronograma confirmado.
- `COMPLETED`: saldo total igual a cero.
- `CANCELLED`: cancelada mediante acción autorizada y motivo.

Cuota, estado calculado:

- `FUTURE`.
- `DUE_TODAY`.
- `OVERDUE`.
- `PARTIALLY_PAID`.
- `PAID`.

Pago:

- `POSTED`.
- `REVERSED`.

Mensaje WhatsApp:

- `QUEUED`.
- `SENT`.
- `DELIVERED`.
- `FAILED`.
- `SKIPPED`.

## 8. Arquitectura funcional

```text
Administrador / Cobrador
            |
          HTTPS
            |
       Aplicación Django
       /       |       \
PostgreSQL   PDF     Trabajo programado
    |                    |
Backups             WhatsApp (fase posterior)
```

La aplicación será una sola unidad desplegable. No se separará en
microservicios. El proceso web y el proceso programado compartirán el mismo
código, reglas y modelos.

## 9. Estructura prevista del repositorio

```text
GestionFinanciera/
|-- app/
|   |-- config/
|   |   |-- settings/
|   |   |   |-- base.py
|   |   |   |-- development.py
|   |   |   `-- production.py
|   |   |-- urls.py
|   |   `-- wsgi.py
|   |-- modules/
|   |   |-- accounts/
|   |   |-- business/
|   |   |-- customers/
|   |   |-- catalog/
|   |   |-- sales/
|   |   |-- collections/
|   |   |-- reports/
|   |   |-- communications/
|   |   `-- audit/
|   |-- templates/
|   |-- static/
|   `-- manage.py
|-- docker/
|   `-- app/
|       `-- entrypoint.sh
|-- scripts/
|   |-- dev.ps1
|   |-- dev.sh
|   |-- test.ps1
|   |-- test.sh
|   |-- backup.ps1
|   |-- backup.sh
|   |-- restore.ps1
|   `-- restore.sh
|-- tests/
|   |-- browser/
|   |-- integration/
|   `-- factories/
|-- docs/
|-- media/
|-- backups/
|-- compose.yaml
|-- Dockerfile
|-- pyproject.toml
|-- .env.example
|-- .gitignore
|-- .gitattributes
`-- README.md
```

Dentro de cada módulo:

```text
models.py       Persistencia y restricciones
services.py     Acciones que cambian estado
selectors.py    Consultas de lectura
forms.py        Validación de formularios
views.py        Flujo HTTP
urls.py         Rutas
admin.py        Soporte administrativo
tests/          Pruebas del módulo
```

Las reglas financieras no se colocarán en plantillas, JavaScript, señales o
vistas. Estarán en servicios explícitos y probados.

## 10. Modelo de datos previsto

| Entidad | Responsabilidad principal |
| --- | --- |
| User | Autenticación, rol y estado |
| BusinessProfile | Nombre, logo, moneda y datos de impresión |
| BusinessRule | Valores predeterminados configurables |
| CollectionWeekday | Días habilitados |
| FrequencyPlan | Semanal/quincenal e intervalo |
| PaymentMethod | Efectivo, transferencia u otro |
| Customer | Datos personales y domicilio |
| Product | Catálogo para ventas y reportes |
| Sale | Contrato y condiciones congeladas |
| Installment | Número, vencimiento y capital planificado |
| Charge | Cuota, recargo u otro débito |
| Payment | Ingreso de dinero |
| PaymentAllocation | Parte de un pago aplicada a un cargo |
| BalanceAdjustment | Corrección excepcional autorizada |
| CollectionAttempt | Resultado de una visita |
| PaymentReversal | Reversión auditable |
| AuditEvent | Quién hizo qué y cuándo |
| MessageTemplate | Plantilla externa |
| MessageDelivery | Envío y estado de WhatsApp |

### Restricciones esenciales

- DNI único cuando está informado.
- Número de cuota único dentro de una venta.
- Fecha de recargo única por cuota.
- Importe de pago mayor que cero.
- Asignaciones no superiores al pago.
- Asignaciones no superiores al saldo aplicable.
- Un pago revertido no puede revertirse dos veces.
- Fechas de cuotas ordenadas.
- Venta activa con al menos una cuota.
- Importe financiado igual a la suma del cronograma.
- Ningún importe financiero usa coma flotante.
- Claves de idempotencia únicas en pagos y recargos.

### Datos congelados en la venta

Aunque cambie la configuración general, cada venta conservará:

- frecuencia;
- intervalo de días;
- cantidad de cuotas;
- recargo diario;
- monto financiado;
- precio contado;
- producto y descripción visibles al vender;
- fecha del primer cobro;
- condiciones acordadas.

## 11. Inventario de pantallas

1. Ingreso.
2. Cambio de contraseña.
3. Dashboard.
4. Lista de clientes.
5. Nuevo cliente.
6. Edición de cliente.
7. Detalle e historial del cliente.
8. Lista de productos.
9. Nuevo/editar producto.
10. Lista de ventas.
11. Nueva venta.
12. Previsualización del cronograma.
13. Detalle de venta.
14. Acción de cancelación.
15. Cobranza de hoy.
16. Cobranza de fecha seleccionada.
17. Registro de pago.
18. Registro de “No pagó”.
19. Reversión de pago.
20. Comprobante de pago.
21. Agenda diaria.
22. Reportes.
23. Configuración del negocio.
24. Métodos de pago.
25. Frecuencias y días.
26. Usuarios y roles.
27. Auditoría.
28. Vista imprimible/PDF.

### 11.1 Menú principal

El menú visible respetará el alcance original:

- Inicio.
- Clientes.
- Ventas.
- Cobranza.
- Agenda diaria.
- Reportes.
- Configuración.

Las opciones se ocultarán o bloquearán según el rol. Ocultar una opción no
reemplaza la verificación de permisos del servidor.

### 11.2 Diccionario funcional de Cliente

| Campo | Regla inicial |
| --- | --- |
| Nombre | Obligatorio |
| Apellido | Obligatorio |
| DNI | Opcional; único cuando se informa |
| Teléfono | Obligatorio para operación; normalizado |
| Dirección | Obligatoria |
| Barrio | Obligatorio o seleccionado de catálogo, a confirmar |
| Referencia de domicilio | Opcional |
| Observaciones | Opcional |
| Estado | Activo/archivado |
| Creado por | Automático |
| Fecha de creación | Automática |
| Última modificación | Automática |

Lista:

- Nombre y apellido.
- Teléfono.
- Dirección.
- Barrio.
- Estado.
- Acciones permitidas.

Acciones:

- Nuevo cliente.
- Editar.
- Archivar.
- Ver historial.
- Registrar venta.
- Ir a cobranza cuando tenga deuda.

### 11.3 Diccionario funcional de Producto

| Campo | Regla inicial |
| --- | --- |
| Nombre | Obligatorio |
| Descripción | Opcional |
| Categoría | Opcional en versión 1 |
| Estado | Activo/inactivo |
| Creado/modificado | Automático |

No se implementará stock en la versión 1. La relación normalizada con ventas
permitirá el reporte de productos más vendidos.

### 11.4 Diccionario funcional de Venta

| Campo | Regla inicial |
| --- | --- |
| Cliente | Obligatorio y activo |
| Producto | Obligatorio y activo al crear |
| Descripción | Copia visible de lo vendido |
| Fecha de entrega | Obligatoria |
| Precio contado | Decimal positivo |
| Monto financiado | Decimal positivo |
| Frecuencia | Semanal/quincenal activa |
| Cantidad de cuotas | Entre 1 y máximo configurado |
| Monto por cuota | Calculado y previsualizado |
| Primer día de cobro | Fecha obligatoria |
| Día de semana | Derivado, no editable |
| Recargo diario | Copiado desde configuración |
| Estado | Borrador/activa/finalizada/cancelada |
| Usuario que registra | Automático |
| Fecha de registro | Automática |

La pantalla no aceptará silenciosamente tres datos incompatibles: monto
financiado, cantidad y monto de cuota. Se elegirá monto financiado y cantidad
como fuente; el cronograma mostrará el importe resultante y la última cuota
absorberá diferencias de centavos.

### 11.5 Diccionario funcional de Cobranza

Columnas o bloques mínimos:

- Cliente.
- Teléfono.
- Dirección.
- Barrio.
- Producto.
- Venta.
- Vencimiento más antiguo.
- Capital exigible.
- Recargo acumulado.
- Días de atraso.
- Total a cobrar.
- Último intento de cobranza.

Acciones:

- Registrar pago.
- No pagó.
- Ver historial.
- Ver venta.
- Ver ubicación/dirección copiable desde celular.

La vista “hoy” incluirá:

- vencimientos exactamente de hoy;
- saldos vencidos anteriores;
- pagos parciales todavía abiertos.

No incluirá cuotas futuras, salvo que el usuario abra expresamente el flujo de
pago anticipado si esa regla se aprueba.

### 11.6 Diccionario funcional de Pago

| Campo | Regla inicial |
| --- | --- |
| Monto total adeudado | Calculado y solo lectura |
| Desglose | Capital, recargos y total |
| Monto abonado | Mayor que cero |
| Saldo posterior | Previsualizado |
| Fecha efectiva | Hoy por defecto; controlada por permiso |
| Hora | Automática |
| Método | Efectivo, transferencia u otro activo |
| Referencia | Opcional; útil para transferencia |
| Observaciones | Opcional |
| Usuario receptor | Automático |
| Comprobante | Número único automático |
| Idempotencia | Token único automático |

Al guardar:

1. se bloquea la deuda relevante;
2. se recalcula el saldo;
3. se valida el importe;
4. se crea el pago;
5. se asigna según la regla aprobada;
6. se calcula el saldo posterior;
7. se actualiza el estado de la venta si corresponde;
8. se registra auditoría;
9. se confirma todo o se revierte todo.

### 11.7 Diccionario funcional de “No pagó”

| Campo | Regla inicial |
| --- | --- |
| Cliente | Derivado de la fila |
| Venta | Derivada o seleccionada |
| Fecha y hora | Automáticas |
| Resultado | No pagó/ausente/prometió pagar/otro |
| Próxima promesa | Opcional |
| Observaciones | Opcional |
| Cobrador | Automático |

Este registro no cambia el saldo y no reemplaza el recargo diario.

### 11.8 Configuración editable

| Configuración | Comportamiento |
| --- | --- |
| Nombre del negocio | Encabezados y PDF |
| Logo | PDF y pantalla |
| Moneda | ARS inicialmente |
| Zona horaria | Buenos Aires inicialmente |
| Recargo diario predeterminado | Nuevas ventas |
| Días de cobranza | Validación y filtros |
| Métodos de pago | Activables/desactivables |
| Frecuencias | Semanal/quincenal |
| Cantidad máxima de cuotas | Validación de nuevas ventas |

Las configuraciones utilizadas históricamente no se eliminarán. Se
desactivarán para preservar ventas y pagos anteriores.

### 11.9 Reportes requeridos

| Reporte | Dimensión principal |
| --- | --- |
| Cobrado hoy | Pagos efectivos del día |
| Cobrado esta semana | Semana local |
| Cobrado este mes | Mes local |
| Clientes morosos | Deuda vencida descendente |
| Clientes al día | Ventas activas sin deuda vencida |
| Total pendiente | Toda la cartera |
| Productos más vendidos | Cantidad de ventas por producto |
| Clientes con mayor deuda | Saldo total descendente |

Cada reporte mostrará:

- periodo;
- fecha/hora de cálculo;
- filtros aplicados;
- total;
- cantidad de registros;
- enlace al detalle cuando corresponda;
- opción CSV cuando sea útil.

### 11.10 Contenido obligatorio del PDF

- Nombre y logo del negocio.
- Título “Cobranza del [día]”.
- Fecha.
- Cliente.
- Dirección.
- Barrio o referencia si se aprueba.
- Producto.
- Total exigible.
- Desglose opcional de capital y recargo.
- Línea de firma.
- Espacio de observaciones.
- Número de página.
- Fecha/hora de generación.

El PDF no expondrá DNI ni teléfono salvo que se apruebe expresamente por
necesidad operativa.

### 11.11 Matriz de trazabilidad

| Requisito original | Fase responsable | Evidencia de cierre |
| --- | --- | --- |
| Dashboard diario | 7 | Totales reconciliados |
| Menú lateral | 2 | Prueba responsive y permisos |
| Clientes | 3 | CRUD, búsqueda y archivado |
| Historial de cliente | 7 | Vista y pruebas históricas |
| Ventas financiadas | 4 | Cronograma validado |
| Frecuencia semanal/quincenal | 4 | Pruebas de fechas |
| Cobranza del día | 5 y 6 | Casos de deuda y concurrencia |
| Recargo diario | 5 | Casos de uno, dos y tres días |
| Pagos parciales | 5 y 6 | Saldo posterior probado |
| No pagó | 6 | Intento sin cambio de saldo |
| Agenda diaria | 7 | Filtros por fecha/día |
| Reportes | 9 | Reconciliación y exportación |
| Planilla A4 | 8 | Impresión física aprobada |
| Configuración | 3 | Cambios sin editar código |
| Seguridad | 2 y 11 | Matriz de permisos y revisión |
| Portabilidad | 1 y 12 | Inicio desde clon limpio |
| Migración de cuadernos | 10 | Acta de saldos |
| Backup y recuperación | 12 | Restauración ensayada |
| WhatsApp | 14 | Envío idempotente |

## 12. Permisos previstos

| Acción | Administrador | Cobrador |
| --- | --- | --- |
| Ver dashboard | Sí | Resumen limitado |
| Ver clientes asignados | Sí | Sí |
| Crear/editar clientes | Sí | No por defecto |
| Archivar clientes | Sí | No |
| Registrar ventas | Sí | No |
| Cancelar ventas | Sí | No |
| Ver agenda | Sí | Sí |
| Registrar pago | Sí | Sí |
| Registrar no pagó | Sí | Sí |
| Revertir pago | Sí | No |
| Ver reportes globales | Sí | No |
| Imprimir planilla | Sí | Sí |
| Cambiar configuración | Sí | No |
| Administrar usuarios | Sí | No |
| Ver auditoría | Sí | No |

Aunque inicialmente exista un solo administrador, el rol Cobrador se modelará
desde el comienzo para no rehacer la seguridad cuando se habilite el celular.

## 13. Fases de desarrollo

### Fase 0. Descubrimiento y cierre de reglas

Objetivo: eliminar ambigüedades antes de diseñar saldos.

Acciones:

1. Crear `REGLAS_NEGOCIO.md`.
2. Responder las decisiones de la sección 6.
3. Tomar tres ventas reales como ejemplos.
4. Reconstruir sus cuotas y pagos manualmente.
5. Crear casos de pago puntual, tardío, parcial y omitido.
6. Definir cancelaciones y perdón de recargos.
7. Definir alcance del cobrador.
8. Definir qué datos de cuadernos se importarán.
9. Confirmar los indicadores.
10. Confirmar los campos de impresión.
11. Preparar wireframes simples.
12. Crear criterios de aceptación de la versión 1.

Aporta el propietario:

- ejemplos reales anonimizados;
- reglas de recargo;
- logo y nombre, si están disponibles;
- forma actual de corregir errores;
- modelo de cuaderno o planilla.

Entregables:

- reglas aprobadas;
- glosario;
- ejemplos calculados;
- alcance congelado;
- wireframes;
- backlog inicial.

Puerta de salida:

- todos los ejemplos tienen un resultado esperado;
- no quedan decisiones financieras críticas sin respuesta.

### Fase 1. Base portable del proyecto

Objetivo: obtener un proyecto vacío reproducible.

Acciones:

1. Crear `pyproject.toml`.
2. Fijar versiones de producción y desarrollo.
3. Crear `Dockerfile` por etapas.
4. Crear `compose.yaml`.
5. Configurar PostgreSQL con volumen nombrado.
6. Crear `.env.example`.
7. Crear `.gitignore` y `.dockerignore`.
8. Crear `.gitattributes`.
9. Crear scripts PowerShell y Bash.
10. Crear proyecto Django.
11. Separar settings de desarrollo y producción.
12. Configurar zona horaria, idioma y archivos estáticos.
13. Crear endpoint de salud.
14. Configurar Ruff y pruebas.
15. Configurar cobertura.
16. Configurar logs estructurados.
17. Ejecutar migración inicial.
18. Añadir CI con PostgreSQL.
19. Documentar inicio y parada.

Dependencias iniciales previstas:

- Django 5.2 LTS;
- psycopg;
- gunicorn;
- WeasyPrint;
- Pillow;
- pytest;
- pytest-django;
- factory-boy;
- coverage;
- Ruff.

Pruebas:

- construcción limpia de la imagen;
- inicio con `docker compose up`;
- conexión real a PostgreSQL;
- endpoint de salud;
- pruebas en contenedor;
- ejecución en un segundo directorio sin rutas absolutas.

Puerta de salida:

- un clon limpio se inicia siguiendo solamente el README.

### Fase 2. Usuarios, seguridad base y diseño visual

Objetivo: iniciar sesión y disponer del esqueleto navegable.

Acciones:

1. Crear modelo de usuario personalizado antes de más migraciones.
2. Crear roles Administrador y Cobrador.
3. Definir permisos.
4. Implementar ingreso y salida.
5. Implementar cambio de contraseña.
6. Crear layout responsive.
7. Crear menú lateral.
8. Crear cabecera y mensajes de confirmación.
9. Crear componentes de tabla, formulario, estado y modal.
10. Empaquetar Bootstrap/HTMX localmente, sin depender de CDN.
11. Comprobar CSRF y cookies.
12. Crear datos de demostración.
13. Añadir página 403 y 404.

Pruebas:

- usuario anónimo redirigido al ingreso;
- cada rol ve solamente sus opciones;
- sesión y cierre correctos;
- menú usable en 360 px de ancho;
- navegación por teclado básica.

Puerta de salida:

- Administrador y Cobrador ingresan y reciben interfaces diferentes.

### Fase 3. Configuración, clientes y productos

Objetivo: administrar los datos maestros.

Acciones:

1. Crear perfil del negocio.
2. Cargar nombre, logo y datos de impresión.
3. Crear métodos de pago configurables.
4. Crear frecuencias configurables con intervalo controlado.
5. Crear días habilitados.
6. Crear clientes.
7. Validar DNI opcional.
8. Normalizar teléfono.
9. Preparar teléfono para formato internacional futuro.
10. Crear búsqueda por nombre, DNI, teléfono y dirección.
11. Crear edición y archivado.
12. Crear productos.
13. Crear búsqueda y desactivación de productos.
14. Crear historial de cambios administrativos.

Pruebas:

- DNI vacío permitido;
- DNI repetido informado rechazado;
- cliente archivado conserva historial;
- producto usado no se borra;
- método de pago usado no se borra;
- logo inválido rechazado;
- filtros y paginación funcionan.

Puerta de salida:

- se pueden preparar todos los datos necesarios para registrar una venta.

### Fase 4. Ventas y generación de cuotas

Objetivo: convertir una venta en un cronograma consistente.

Acciones:

1. Crear formulario de venta.
2. Seleccionar cliente y producto.
3. Guardar descripción comercial congelada.
4. Registrar entrega, precio contado y monto financiado.
5. Elegir frecuencia y cantidad.
6. Calcular monto sugerido por cuota.
7. Previsualizar todas las fechas.
8. Validar primer día de cobro.
9. Derivar día de semana.
10. Ajustar diferencia en última cuota.
11. Confirmar la venta dentro de una transacción.
12. Crear cuotas y cargos de capital.
13. Crear detalle y cronograma.
14. Implementar finalización automática.
15. Implementar cancelación según regla aprobada.
16. Prohibir edición destructiva de una venta activa.

Servicios centrales:

- `preview_installment_schedule()`;
- `create_sale()`;
- `activate_sale()`;
- `cancel_sale()`;
- `complete_sale_if_settled()`.

Pruebas:

- 12 cuotas semanales;
- cuotas quincenales;
- cambio de mes y año;
- años bisiestos;
- diferencia de centavos;
- monto inconsistente;
- primer cobro anterior a entrega;
- doble confirmación;
- rollback total si falla una cuota.

Puerta de salida:

- la suma del cronograma coincide exactamente con el monto financiado.

### Fase 5. Libro de deuda, recargos y saldos

Objetivo: construir la fuente única de verdad financiera.

Acciones:

1. Crear cargos auditables.
2. Crear pagos.
3. Crear asignaciones de pago.
4. Crear ajustes autorizados.
5. Crear reversión de pago.
6. Implementar saldo por cargo.
7. Implementar saldo por cuota.
8. Implementar saldo por venta.
9. Implementar saldo por cliente.
10. Implementar saldo de cartera.
11. Crear generación idempotente de recargos.
12. Crear comando de puesta al día hasta una fecha.
13. Crear restricción que impida recargo duplicado.
14. Congelar tasa de recargo por venta.
15. Implementar consultas históricas “a fecha de”.
16. Registrar auditoría.

La tarea de recargo:

1. recibe una fecha;
2. identifica cuotas vencidas con saldo al inicio del día;
3. genera solamente cargos faltantes;
4. usa la tasa congelada de la venta;
5. puede ejecutarse varias veces sin duplicar;
6. recupera días omitidos si el servidor estuvo apagado;
7. registra inicio, fin, cantidad y errores.

Pruebas financieras mínimas:

- $20.000 el vencimiento;
- $25.000 con un día tarde y recargo de $5.000;
- $30.000 con dos días;
- pago parcial;
- varias cuotas vencidas;
- varias ventas;
- cambio de recargo global;
- ejecución doble del comando;
- servidor apagado tres días;
- pago y recargo simultáneos;
- reversión;
- consulta histórica.

Puerta de salida:

- cada saldo puede demostrarse sumando cargos y restando créditos.

### Fase 6. Operación de cobranza

Objetivo: crear la pantalla principal de trabajo.

Acciones:

1. Crear consulta de cobranza por fecha.
2. Incluir deuda anterior y vencimientos del día.
3. Agrupar visualmente por cliente.
4. Mostrar dirección, producto, cuota, atraso y total.
5. Ordenar por barrio, dirección, nombre o deuda.
6. Crear filtros.
7. Crear registro de pago.
8. Mostrar desglose antes de confirmar.
9. Asignar automáticamente a deuda antigua.
10. Permitir asignación manual solamente al administrador.
11. Crear comprobante.
12. Crear botón “No pagó”.
13. Registrar observaciones de visita.
14. Evitar doble envío del formulario.
15. Añadir token de idempotencia.
16. Bloquear filas financieras durante el pago.
17. Actualizar totales sin recargar toda la página.
18. Crear reversión administrativa.

Pruebas:

- pago total;
- pago parcial;
- pago exacto de recargo;
- intento de pago cero;
- intento de sobrepago;
- doble clic;
- dos usuarios pagando a la vez;
- pago de deuda con dos cuotas;
- pago revertido;
- no pagó repetido;
- permisos del cobrador.

Puerta de salida:

- dos solicitudes simultáneas no pueden cobrar dos veces el mismo saldo.

### Fase 7. Dashboard, agenda e historial

Objetivo: presentar información operativa y explicable.

Acciones:

1. Crear tarjetas del dashboard.
2. Mostrar fecha local correcta.
3. Mostrar clientes a cobrar.
4. Mostrar monto esperado.
5. Mostrar atrasados.
6. Mostrar cartera total.
7. Mostrar cobrado hoy.
8. Enlazar con cobranza.
9. Crear agenda con selector de fecha.
10. Crear accesos por día de semana.
11. Crear historial del cliente.
12. Separar ventas, cuotas, cargos, pagos e intentos.
13. Mostrar total abonado y saldo.
14. Mostrar cantidad de atrasos.
15. Permitir navegación a venta y comprobante.
16. Crear estados vacíos claros.

Pruebas:

- cliente contado una sola vez aunque tenga varias cuotas;
- límites de medianoche;
- consulta de una fecha pasada;
- consulta de fecha futura;
- métricas iguales a consultas del libro;
- usuario cobrador no ve datos restringidos.

Puerta de salida:

- las tarjetas coinciden con la suma detallada de la agenda.

### Fase 8. Planilla diaria y PDF A4

Objetivo: reemplazar la planilla manual sin perder espacio operativo.

Acciones:

1. Crear plantilla HTML de impresión.
2. Configurar `@page` A4.
3. Definir márgenes y tipografía.
4. Añadir negocio, logo, fecha y título.
5. Añadir cliente, dirección, producto y deuda.
6. Añadir firma y observaciones.
7. Crear saltos de página seguros.
8. Repetir encabezado cuando corresponda.
9. Ordenar igual que la agenda.
10. Añadir fecha/hora de generación.
11. Añadir número de página.
12. Generar PDF con WeasyPrint.
13. Añadir vista previa HTML.
14. Probar impresoras y escalado.

Pruebas:

- 1, 10, 18 y 100 clientes;
- direcciones largas;
- nombres largos;
- logo grande o transparente;
- deuda con varias cuotas;
- caracteres acentuados;
- sin cortes sobre firma;
- PDF reproducible dentro del contenedor.

Puerta de salida:

- una impresión real en A4 es legible y tiene espacio suficiente.

### Fase 9. Reportes y exportaciones

Objetivo: responder preguntas de gestión usando el mismo libro.

Acciones:

1. Cobrado hoy.
2. Cobrado esta semana.
3. Cobrado este mes.
4. Clientes morosos.
5. Clientes al día.
6. Total pendiente.
7. Productos más vendidos.
8. Clientes con mayor deuda.
9. Filtros de fecha.
10. Exportación CSV.
11. Totales y subtotales.
12. Enlaces al detalle.
13. Índices de base para consultas.
14. Protección contra consultas excesivas.

Pruebas:

- semanas que cruzan mes;
- meses que cruzan año;
- pagos revertidos;
- clientes archivados;
- ventas canceladas;
- exportación con acentos;
- totales iguales al libro;
- rendimiento con datos voluminosos.

Puerta de salida:

- todos los totales se reconcilian con pagos y cargos individuales.

### Fase 10. Importación de cuadernos

Objetivo: comenzar a operar con la deuda existente.

Acciones:

1. Inventariar calidad de datos.
2. Elegir importación completa o saldo de apertura.
3. Preparar plantilla CSV.
4. Crear validación sin escritura.
5. Informar errores por fila.
6. Detectar duplicados.
7. Crear comando de importación idempotente.
8. Conservar identificador de origen.
9. Importar a una base de ensayo.
10. Comparar clientes, ventas y saldos.
11. Corregir archivo.
12. Repetir hasta reconciliar.
13. Guardar acta de totales iniciales.
14. Importar en producción.

Si solamente se conoce el saldo, se cargará como saldo de apertura auditado. No
se inventarán pagos históricos.

Pruebas:

- CSV válido;
- filas incompletas;
- DNI repetido;
- importación ejecutada dos veces;
- caracteres y fechas argentinas;
- totales antes y después;
- rollback si falla el lote.

Puerta de salida:

- total importado aprobado contra el control manual.

### Fase 11. Calidad, seguridad y rendimiento

Objetivo: preparar el sistema para datos financieros reales.

Acciones:

1. Revisar permisos de todas las vistas.
2. Revisar CSRF.
3. Configurar HTTPS obligatorio.
4. Configurar cookies seguras.
5. Configurar hosts permitidos.
6. Separar secretos.
7. Proteger intentos de ingreso.
8. Revisar carga de archivos.
9. Limitar tamaño y tipo de logo.
10. Evitar datos sensibles en logs.
11. Revisar dependencias vulnerables.
12. Aplicar cabeceras de seguridad.
13. Revisar consultas N+1.
14. Añadir índices.
15. Probar concurrencia.
16. Probar recuperación ante errores.
17. Medir cobertura.
18. Ejecutar pruebas completas en contenedor limpio.

Objetivos iniciales de rendimiento:

- dashboard habitual menor a 2 segundos;
- agenda habitual menor a 2 segundos;
- registro de pago menor a 2 segundos;
- PDF de 100 clientes menor a 15 segundos;
- listados siempre paginados.

Puerta de salida:

- no quedan hallazgos críticos o altos abiertos.

### Fase 12. Backups, despliegue y observabilidad

Objetivo: ejecutar fuera de la PC de desarrollo de forma recuperable.

Acciones:

1. Elegir proveedor y región.
2. Crear entorno de staging.
3. Configurar dominio.
4. Configurar HTTPS.
5. Crear base PostgreSQL.
6. Configurar usuario de base con mínimo privilegio.
7. Configurar almacenamiento persistente de media.
8. Configurar variables y secretos.
9. Ejecutar migraciones como tarea de despliegue.
10. Servir estáticos.
11. Crear comprobación de salud.
12. Configurar logs y alertas.
13. Configurar backups diarios.
14. Definir retención.
15. Descargar copia externa periódica.
16. Restaurar un backup en staging.
17. Documentar rollback.
18. Documentar renovación y actualización.

Política inicial de backup:

- copia diaria;
- retención diaria de 30 días;
- copia mensual adicional;
- copia antes de cada migración importante;
- prueba de restauración mensual;
- cifrado y acceso restringido;
- al menos una copia fuera del servidor principal.

Puerta de salida:

- una base vacía puede restaurarse y volver a operar siguiendo el manual.

### Fase 13. Prueba de aceptación y piloto

Objetivo: validar con trabajo real antes del corte definitivo.

Acciones:

1. Crear guion de aceptación.
2. Capacitar al administrador.
3. Cargar un conjunto piloto.
4. Operar en paralelo con el cuaderno.
5. Comparar diariamente cobros y saldos.
6. Registrar incidencias.
7. Corregir y volver a probar.
8. Probar planilla en recorrido real.
9. Probar celular con conectividad real.
10. Probar recuperación de contraseña.
11. Probar backup y restore.
12. Aprobar corte.
13. Tomar backup previo.
14. Importar saldo final.
15. Comenzar producción.

Duración recomendada del paralelo: al menos un ciclo completo de cobranza y,
preferentemente, dos.

Puerta de salida:

- cero diferencias de saldo sin explicación;
- flujos críticos aprobados por el usuario.

### Fase 14. WhatsApp Business

Objetivo: enviar recordatorios después de estabilizar la cobranza.

Acciones:

1. Confirmar necesidad y presupuesto.
2. Normalizar teléfonos.
3. Registrar consentimiento y opción de baja.
4. Configurar Meta Business.
5. Configurar número.
6. Crear plantillas de utilidad.
7. Obtener aprobación.
8. Guardar secretos fuera del código.
9. Añadir cola y worker.
10. Programar selección de destinatarios.
11. Crear clave idempotente por cliente, fecha y plantilla.
12. Enviar.
13. Recibir webhooks.
14. Registrar entregado, leído o fallido cuando esté disponible.
15. Reintentar errores recuperables.
16. Evitar mensajes duplicados.
17. Crear panel de resultados.
18. Añadir límites y corte de emergencia.

Pruebas:

- número válido e inválido;
- cliente sin consentimiento;
- plantilla rechazada;
- API no disponible;
- webhook repetido;
- reintento;
- ejecución doble de tarea;
- exclusión de deuda cancelada.

Puerta de salida:

- ningún cliente recibe dos veces el mismo recordatorio.

### Fase 15. Cierre y mantenimiento

Objetivo: declarar el proyecto finalizado y sostenible.

Acciones:

1. Revisar criterios de la sección 2.
2. Cerrar incidencias críticas.
3. Actualizar manual de usuario.
4. Actualizar manual técnico.
5. Documentar recuperación.
6. Documentar importación/exportación.
7. Crear versión y etiqueta.
8. Guardar backup de cierre.
9. Crear calendario de mantenimiento.
10. Definir responsable operativo.

Mantenimiento:

- revisar errores semanalmente;
- verificar backup diariamente de forma automática;
- probar restauración mensualmente;
- actualizar parches de seguridad mensualmente;
- revisar usuarios trimestralmente;
- archivar métodos y productos no usados;
- revisar capacidad de disco y base;
- renovar dominio/certificados/servicios.

Puerta de salida:

- otra persona puede operar y recuperar el sistema usando la documentación.

## 14. Casos de prueba de aceptación obligatorios

1. Cliente nuevo con DNI.
2. Cliente nuevo sin DNI.
3. DNI duplicado.
4. Venta de $480.000 en 12 cuotas de $40.000.
5. Venta cuyo monto necesita ajuste de centavos.
6. Cuota pagada el día correcto.
7. Cuota con uno, dos y tres días de atraso.
8. Pago parcial.
9. Segundo recargo después de pago parcial.
10. Dos cuotas vencidas.
11. Dos ventas del mismo cliente.
12. Pago general según regla aprobada.
13. Doble clic en guardar.
14. Dos usuarios intentando cobrar.
15. Reversión de pago.
16. Cliente marcado no pagó.
17. Cambio del recargo global.
18. Venta antigua conserva recargo anterior.
19. Domingo/feriado según regla aprobada.
20. Venta finalizada automáticamente.
21. Venta cancelada.
22. Cliente archivado con historial.
23. Reporte diario.
24. Reporte semanal.
25. Reporte mensual.
26. PDF con 18 clientes.
27. PDF con nombres y direcciones largas.
28. Importación duplicada.
29. Backup restaurado.
30. Cobrador intentando entrar a configuración.

## 15. Pruebas automáticas

### Unitarias

- cronogramas;
- reglas de recargo;
- asignación de pagos;
- estados derivados;
- métricas;
- formateo monetario;
- permisos simples.

### Integración

- transacciones PostgreSQL;
- bloqueo concurrente;
- restricciones;
- comandos diarios;
- importación;
- reversión;
- reportes.

### Navegador

- ingreso;
- alta de cliente;
- venta;
- pago;
- no pagó;
- agenda;
- PDF;
- permisos.

### Visuales

- escritorio;
- teléfono;
- estados vacíos;
- errores;
- impresión A4;
- contraste y legibilidad.

### Recuperación

- backup;
- restauración;
- migración fallida;
- servidor reiniciado;
- tarea diaria omitida.

## 16. Seguridad mínima obligatoria

- HTTPS en producción.
- Base de datos no expuesta a Internet.
- Contraseñas hash de Django.
- Usuario administrador individual, no compartido.
- Permisos por rol.
- CSRF.
- Cookies `Secure`, `HttpOnly` y política `SameSite`.
- Secretos en entorno.
- Archivos subidos validados.
- Auditoría de pagos, reversas, ajustes y cancelaciones.
- Bloqueo o demora de intentos repetidos de ingreso.
- Dependencias con parches.
- Backups cifrados o protegidos.
- Restauración probada.
- Logs sin contraseñas, tokens o datos completos innecesarios.
- Sesiones revocables.
- Eliminación física restringida.

## 17. Portabilidad obligatoria

El proyecto no se aceptará como portable si solamente funciona en esta PC.

Debe cumplir:

- inicio con Docker Compose;
- modo nativo documentado;
- rutas relativas;
- configuración externa;
- versiones fijadas;
- scripts PowerShell y Bash;
- archivos estáticos locales;
- PDF dentro de Linux;
- base exportable;
- media exportable;
- migraciones reproducibles;
- CI en Linux;
- instrucciones desde un clon limpio;
- ningún secreto en Git.

## 18. Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| Regla de recargo ambigua | Cerrar ejemplos antes de programar |
| Saldo modificado manualmente | Libro de movimientos y ajustes auditados |
| Pago duplicado | Idempotencia, transacción y bloqueo |
| Cambio de configuración retroactivo | Congelar condiciones en la venta |
| Datos de cuaderno incompletos | Saldo de apertura explícito |
| Diferencias de reportes | Una sola fuente de consultas |
| Caída nocturna | Tarea idempotente con puesta al día |
| Pérdida de datos | Backups y restauraciones ensayadas |
| Mala señal en la calle | PDF como respaldo; offline después |
| Alcance creciente | Separar versión 1 y ampliaciones |
| Dependencia de esta PC | Contenedores y despliegue externo |
| Dependencia de WhatsApp | No usarlo para iniciar la operación |
| Error de fecha/zona | Fechas locales probadas y almacenamiento consistente |
| Disco de Docker creciendo | Control periódico y limpieza documentada |
| Eliminación accidental | Archivado y permisos |

## 19. Cronograma orientativo

La duración real depende de las decisiones y de la validación del usuario. Para
una ejecución enfocada:

| Bloque | Estimación orientativa |
| --- | --- |
| Fases 0-2 | 1 a 2 semanas |
| Fases 3-4 | 1 a 2 semanas |
| Fases 5-6 | 2 a 3 semanas |
| Fases 7-9 | 1 a 2 semanas |
| Fases 10-13 | 2 a 4 semanas |
| WhatsApp | 1 a 2 semanas más tiempos de Meta |

Una versión 1 responsable se estima en 7 a 13 semanas de trabajo enfocado. No
se reducirá tiempo eliminando pruebas financieras, backups o piloto.

## 20. Definición de terminado

Una tarea está terminada cuando:

- código implementado;
- revisión propia completada;
- migraciones incluidas;
- pruebas creadas;
- pruebas ejecutadas;
- permisos revisados;
- interfaz responsive comprobada;
- errores tratados;
- documentación actualizada;
- usuario validó el resultado si es funcional.

El proyecto está terminado cuando:

- todas las funciones obligatorias están aceptadas;
- los casos críticos pasan;
- los totales se reconcilian;
- el PDF fue impreso;
- el sistema fue restaurado desde backup;
- el piloto terminó sin diferencias inexplicables;
- la documentación permite operar y recuperar;
- existe una versión identificable y un backup de cierre.

## 21. Próximas acciones inmediatas

1. Crear `docs/REGLAS_NEGOCIO.md`.
2. Confirmar o corregir las reglas propuestas.
3. Aportar tres ejemplos reales anonimizados.
4. Definir qué datos se migrarán.
5. Crear wireframes.
6. Cerrar fase 0.
7. Construir el esqueleto portable de la fase 1.

No se comenzará por reportes o WhatsApp. La primera entrega funcional vertical
será:

```text
cliente -> venta -> cuotas -> deuda de una fecha -> pago parcial -> saldo
```

Cuando esa cadena sea correcta y esté probada se construirán dashboard,
impresión y reportes sobre ella.
