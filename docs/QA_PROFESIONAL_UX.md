# Plan profesional de QA y experiencia de uso

## Objetivo

Validar que el sistema sea correcto, fácil de entender y estable antes de cada
entrega. La revisión se realiza con una base ficticia aislada: nunca se usa la
base del cliente para probar altas, pagos, anulaciones o borrados.

## 0. Preparación segura

1. Cerrar el sistema y comprobar que no quede un proceso usando la base.
2. Crear una copia ZIP restaurable y verificar su integridad SQLite.
3. Anotar versión, fecha, equipo, Windows y navegador utilizados.
4. Crear una carpeta temporal para `data`, `backups`, `exports`, `media` y
   `storage`.
5. Ejecutar migraciones y cargar los datos ficticios.
6. Confirmar el punto de partida: 50 clientes, 70 ventas y 5 cobradores.

Resultado esperado: cualquier prueba destructiva afecta únicamente la copia
temporal.

## 1. Control automático

Ejecutar desde la carpeta del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\FaseFinal3-QA.ps1
```

Debe aprobar:

- análisis estático;
- validación de Django;
- control de migraciones pendientes;
- suite completa y cobertura mínima;
- rutas principales y archivos estáticos;
- creación, apertura y restauración de copias;
- construcción y prueba aislada del portable.

Un error, una excepción HTTP 500 o una migración olvidada detienen la entrega.

## 2. Recorridos funcionales

Probar de principio a fin, sin saltar pantallas:

1. Crear y editar un cliente.
2. Crear y archivar un producto.
3. Registrar una venta semanal, cada 2 semanas y mensual.
4. Probar pago inicial aparte, cuota pagada al entregar e ingreso histórico.
5. Registrar pago total, parcial, atrasado y adelantado.
6. Registrar “No pagó”, otro resultado y anular un pago.
7. Preparar planillas, asignar clientes y revisar el historial del cobrador.
8. Imprimir cobranza y resumen del cliente.
9. Cancelar y editar una venta; comprobar el Archivo seguro.
10. Crear copia, exportar CSV y restaurar en una carpeta temporal.

En cada paso se compara Inicio, Cobranza, Semana, Cliente, Venta y Reportes. Los
totales deben cambiar juntos y no puede quedar información activa dentro del
Archivo seguro, ni información cancelada en las pantallas de trabajo.

## 3. Pruebas de exactitud financiera

Usar importes con centavos y fechas límite:

- $0,01; $9.999.999,99 y valores máximos admitidos;
- una y la cantidad máxima de cuotas;
- vencimiento hoy, ayer, domingo y fin de mes;
- febrero y año bisiesto;
- pago exactamente igual, menor y mayor al pendiente;
- varias cuotas vencidas con un único recargo diario por venta;
- anulación y nuevo registro del pago;
- dos pestañas intentando guardar la misma operación.

La suma del detalle siempre debe coincidir con el total mostrado. No se aceptan
diferencias por redondeo ni operaciones duplicadas.

## 4. Usabilidad, lenguaje y accesibilidad

Para cada pantalla se comprueba:

- una acción principal evidente;
- botones con verbo y resultado: “Guardar pago”, “Mostrar día”, “Abrir
  planilla”;
- “Cancelar” solo abandona el formulario; “Cancelar venta” cambia el estado;
- avisos que expliquen cómo corregir el problema;
- foco de teclado visible y orden lógico con `Tab`;
- sección actual identificada en el menú;
- campos con etiqueta, ayuda y error próximos;
- estado vacío que explique qué falta y qué hacer;
- ausencia de términos técnicos innecesarios;
- uso uniforme de voseo y vocabulario habitual en Argentina.

Palabras preferidas: cliente, venta, cuota, cobranza, recargo, medio de pago,
planilla, copia de seguridad y Archivo seguro. “Recorrido” puede usarse para el
trabajo realizado por el cobrador, pero la acción de preparar o imprimir se
expresa como “planilla”.

## 5. Matriz visual y responsive

Revisar al menos estos tamaños:

| Tipo | Resolución mínima |
| --- | --- |
| Escritorio amplio | 1920 × 1080 |
| Notebook común | 1366 × 768 |
| Tablet | 768 × 1024 |
| Celular habitual | 390 × 844 |
| Celular angosto | 360 × 800 |

Pantallas obligatorias: Inicio, Clientes, detalle de cliente, Productos,
Ventas, formulario de venta, detalle de venta, Cobranza, pago, Semana,
planillas por cobrador, historial de cobradores, Reportes, Configuración,
Archivo seguro y Datos y respaldo.

Criterios:

- ningún texto, importe, campo o botón sale de su tarjeta;
- nunca aparece desplazamiento horizontal de toda la página;
- las tablas se transforman en fichas o mantienen un desplazamiento local;
- los botones táctiles miden al menos 44 px de alto;
- el menú muestra la sección activa;
- los importes largos no pisan etiquetas ni acciones;
- el zoom del navegador al 125 % y 150 % sigue siendo utilizable;
- la impresión A4 no corta clientes entre páginas.

## 6. Robustez y uso incorrecto

Sin modificar los archivos internos, intentar:

- doble clic rápido en Guardar;
- volver atrás y reenviar un formulario;
- abrir dos o más pestañas;
- dejar campos obligatorios vacíos;
- nombres, domicilios y observaciones muy largos;
- caracteres especiales, comillas, emojis y texto similar a HTML;
- fechas fuera de orden;
- archivar elementos todavía relacionados;
- editar o borrar desde una URL antigua;
- interrumpir una exportación o cerrar durante una copia.

El sistema debe rechazar la acción con un mensaje comprensible, conservar la
contabilidad y registrar el error técnico en el log sin mostrar una pantalla
500 al usuario.

## 7. Evidencia y criterio de entrega

Guardar:

- resultado de la suite;
- versión y SHA-256 del ZIP;
- capturas de escritorio y celular;
- lista de incidencias con severidad, reproducción, esperado y obtenido;
- prueba de restauración;
- base ficticia utilizada, nunca datos del cliente.

Severidades:

- **P0:** pérdida o corrupción de datos; bloquea inmediatamente.
- **P1:** cálculo incorrecto o función principal inutilizable; bloquea entrega.
- **P2:** confusión importante, desborde o flujo incompleto; corregir antes de
  entregar salvo aceptación expresa.
- **P3:** detalle cosmético sin impacto operativo; puede planificarse.

La versión se entrega únicamente con cero P0, P1 y P2 abiertos, suite aprobada,
restauración comprobada y revisión visual sin desbordes.
