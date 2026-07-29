# FaseFinal2: auditoría integral

## Dictamen

La arquitectura es adecuada para el uso definido: una persona, una PC,
funcionamiento local y carga manual. Django aporta reglas y pantallas; SQLite
conserva toda la información relacional en un archivo; el paquete PyInstaller
evita exigir Python instalado.

No es una aplicación multiempresa, multiusuario, de inventario ni de trabajo
simultáneo desde varias computadoras. Esas ausencias son decisiones de alcance,
no defectos para este caso.

## Revisión por módulo

| Área | Verificación | Resultado |
|---|---|---|
| Clientes | alta, edición, archivo, búsqueda, detalle e historial | Aprobado |
| Productos | alta, edición, archivo, búsqueda y uso histórico | Aprobado |
| Ventas | precio, entrega, total en cuotas, 3 frecuencias y estados | Aprobado |
| Cuotas | reparto exacto, fechas semanales/quincenales/mensuales | Aprobado |
| Cobranza | exigible por fecha, atraso, recargo y WhatsApp manual | Aprobado |
| Pagos | total, parcial, entrega inicial, métodos y anulación | Aprobado |
| Semana | lunes a sábado, programado, arrastre y barrios | Aprobado |
| Historial | ventas, cuotas, pagos, visitas y línea temporal | Aprobado |
| Reportes | día, semana, mes, deuda, clientes y productos | Aprobado |
| Impresión | planilla diaria preparada para A4 | Aprobado |
| Configuración | negocio, logo, recargo, frecuencias y métodos | Aprobado |
| Datos | backup comprimido, exportación CSV y restaurador | Aprobado |
| Portable | ejecutable, estáticos, migración, backup y restauración | Aprobado |

## Hallazgos corregidos

### Rendimiento de saldos y recargos

Con 48 ventas, 325 cuotas y 1.578 recargos, el Dashboard realizaba consultas
repetidas por cada cuota.

| Pantalla | Antes | Después |
|---|---:|---:|
| Dashboard | 7.400 consultas / 2,78 s | 22 consultas / 0,26 s |
| Cobranza | 1.595 consultas / 2,63 s | 13 consultas / 0,12 s |
| Semana | más de 3 s | 40 consultas / 0,52 s |
| Reportes | más de 2 s | 16 consultas / 0,10 s |

Los valores son una medición local orientativa, no una promesa de tiempo para
cualquier PC. La regresión quedó protegida con límites de consultas en tests.

### Fechas extremas

Fechas como `0001-01-01` o `9999-12-31` podían desbordar al avanzar o retroceder
una semana. Ahora se descartan como navegación inválida y la pantalla vuelve a
la fecha local.

### Consultas históricas

Una venta cancelada o un pago anulado se estaba interpretando por su estado
actual incluso al mirar un día anterior. Ahora:

- la venta sigue formando parte de una fecha previa a su cancelación;
- deja de ser exigible desde la fecha de cancelación;
- un pago cuenta antes de su anulación;
- deja de reducir la deuda desde la fecha de anulación.

### Configuración de WhatsApp

Una llave mal cerrada o una variable inexistente podía provocar error 500 en
Cobranza. El formulario admite solamente `{nombre}`, `{monto}` y
`{vencimiento}`. Además existe un mensaje seguro de reserva para bases antiguas.

### Métodos de pago

El texto configurable podía superar el tamaño del campo que guarda un pago.
Ahora se aceptan hasta 20 métodos y 40 caracteres por método.

### Exportación CSV

La protección contra fórmulas de Excel ahora también reconoce espacios antes de
`=`, `+`, `-` o `@`.

## Integridad financiera comprobada

- la suma de las cuotas coincide exactamente con el total en cuotas;
- los centavos residuales se distribuyen sin perder ni crear dinero;
- la suma de aplicaciones de un pago coincide con el pago;
- el recargo no se duplica al abrir nuevamente una pantalla;
- el pago parcial conserva el saldo;
- el pago se aplica primero a recargos y después a capital;
- una clave de operación repetida no duplica un pago;
- los pagos anulados dejan trazabilidad;
- las ventas canceladas dejan trazabilidad y no son cobrables desde su fecha.

## Portabilidad y recuperación

La carpeta portable contiene cuatro áreas que deben viajar juntas:

- `data`: base SQLite y clave local;
- `backups`: copias restaurables comprimidas;
- `exports`: ZIP de CSV para consulta externa;
- `media`: logo y otros archivos cargados.

El ZIP CSV no reemplaza al backup: es una exportación legible, no una
restauración automática. El restaurador reemplaza la base completa; no mezcla
dos carteras. Para archivar una ubicación y comenzar otra, se conserva una copia
completa de la carpeta portable y se inicia otra carpeta.

## Límites conocidos

- SQLite es apropiado para una persona; no se certifica edición simultánea desde
  varias PCs.
- WhatsApp abre un mensaje listo para enviar; no lo envía automáticamente.
- No hay stock, costo de compra, ganancia, caja contable ni devolución de una
  entrega inicial al cancelar. Son funciones fuera del alcance actual.
- La exportación arma archivos CSV completos en memoria. Es adecuada para el
  tamaño personal ensayado; una cartera de cientos de miles de ventas y millones
  de cuotas requeriría exportación por flujo y pruebas de carga específicas.
- El backup de base no incluye `media`; para una mudanza total debe copiarse la
  carpeta portable completa.
- No existe importación/mezcla de CSV. La recuperación oficial es mediante el
  backup SQLite o conservando la carpeta entera.

## Recomendación

La versión es apta para prueba funcional completa con datos ficticios. Antes de
usarla como único registro real conviene operarla algunos días en paralelo con
el método anterior y comprobar una restauración en una copia.

