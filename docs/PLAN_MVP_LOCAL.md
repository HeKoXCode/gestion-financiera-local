# Plan definitivo: aplicación local monousuario

Versión: 1.0  
Objetivo: MVP funcional y portable en 2–3 días de trabajo concentrado  
Usuario: una sola persona  
Modo de uso: local, manual y principalmente offline

Estado al 24/07/2026:

- Paso 0 terminado: reglas financieras documentadas.
- Paso 1 terminado: base local portable.
- Paso 2 terminado: modelos, restricciones, configuración y motor base.
- Paso 3 terminado: clientes, productos, ventas, cuotas e interfaz responsive.
- Paso 4 terminado: recargos automáticos, cobranza, pagos, anulaciones y visitas.
- Paso 5 terminado: dashboard, vista semanal e historial consolidado.
- Paso 6 terminado: planilla A4, reportes operativos y configuración visual.
- Paso 7 terminado: backups automáticos y manuales, recuperación reciente,
  exportación ZIP/CSV y restauración segura.
- Paso 8 terminado: 20 casos de aceptación, ejecutables, prueba aislada,
  manifiesto, ZIP portable y manual.
- Estado final: MVP terminado.

## 1. Cambio de enfoque

El sistema no se diseñará como plataforma empresarial ni como servicio en la
nube. Será un programa local para una persona que necesita:

- abrir el sistema;
- consultar qué debe cobrar hoy o un día determinado;
- cargar clientes;
- registrar ventas financiadas;
- registrar pagos y pagos parciales;
- conocer atrasos y recargos;
- consultar historiales;
- imprimir una planilla diaria;
- obtener reportes simples;
- respaldar y exportar los datos.

Se eliminan del MVP:

- usuarios y permisos;
- inicio de sesión;
- servidor público;
- HTTPS;
- PostgreSQL;
- Docker como requisito diario;
- tareas distribuidas;
- auditoría empresarial;
- API;
- nube;
- WhatsApp Business API;
- Power BI;
- aplicación móvil nativa.

No se eliminan:

- clientes;
- productos;
- ventas;
- cuotas;
- recargos;
- pagos parciales;
- saldos;
- semana;
- historial;
- dashboard;
- reportes;
- impresión A4;
- configuración;
- backup;
- exportación.

## 2. Tecnología simplificada

| Componente | Decisión |
| --- | --- |
| Lenguaje | Python 3.12 |
| Aplicación | Django 5.2 LTS |
| Base de datos | SQLite |
| Interfaz | HTML, CSS y Bootstrap local |
| Ejecución | Servidor local en `127.0.0.1` |
| Apertura | Acceso directo o ejecutable |
| Impresión | Vista HTML con CSS A4 y diálogo del navegador |
| PDF | “Guardar como PDF” desde el navegador |
| Backup | Copia consistente de SQLite |
| Exportación | ZIP con CSV en UTF-8 |
| Empaquetado | PyInstaller en modo carpeta |
| WhatsApp | Enlace manual con mensaje precargado |

Django se conserva porque permite implementar formularios, relaciones,
validaciones, reportes y plantillas rápidamente. SQLite es suficiente para una
persona y guarda toda la base en un archivo portable.

Docker seguirá instalado como herramienta disponible, pero no será necesario
para abrir ni utilizar el programa.

## 3. Experiencia de uso final

1. La persona hace doble clic en `GestionFinanciera.exe` o `Iniciar.bat`.
2. El programa valida la base de datos.
3. Crea una copia de seguridad de inicio si corresponde.
4. Aplica recargos diarios faltantes.
5. Abre automáticamente el navegador.
6. Muestra el dashboard y la cobranza del día.
7. La persona trabaja normalmente.
8. Puede crear un backup o exportar CSV en cualquier momento.
9. Presiona “Cerrar y respaldar”.
10. El programa crea una copia final y se cierra.

Si el equipo se apaga inesperadamente, SQLite protege las transacciones y
existirá una copia de recuperación reciente.

## 4. Estructura portable

```text
GestionFinanciera/
|-- app/
|   |-- config/
|   |-- modules/
|   |-- templates/
|   |-- static/
|   `-- manage.py
|-- launcher/
|   |-- launcher.py
|   |-- restorer.py
|   `-- backup.py
|-- data/
|   `-- gestion_financiera.sqlite3
|-- backups/
|-- exports/
|-- media/
|-- portable/
|-- scripts/
|   |-- Iniciar.bat
|   |-- Desarrollo.ps1
|   |-- Probar.ps1
|   |-- ProbarPortable.ps1
|   `-- ConstruirPortable.ps1
|-- portable_assets/
|-- tests/
|-- docs/
|-- GestionFinanciera.spec
|-- requirements.lock
|-- pyproject.toml
`-- README.md
```

Las carpetas `data`, `backups`, `exports` y `media` estarán separadas del
código. Actualizar el programa no deberá reemplazar los datos.

## 5. Base de datos simplificada

### Configuración

- nombre del negocio o persona;
- logo;
- recargo diario;
- días de cobranza;
- métodos de pago;
- frecuencias disponibles;
- cantidad máxima de cuotas;
- mensaje predeterminado de WhatsApp.

### Cliente

- nombre;
- apellido;
- DNI opcional;
- teléfono;
- dirección;
- barrio;
- referencia;
- observaciones;
- activo/inactivo;
- fechas de creación y modificación.

### Producto

- nombre;
- descripción;
- activo/inactivo.

### Venta

- cliente;
- producto;
- descripción congelada;
- fecha de entrega;
- precio contado;
- monto financiado;
- frecuencia semanal o quincenal;
- cantidad de cuotas;
- recargo diario congelado;
- primer vencimiento;
- estado activa/finalizada/cancelada.

### Cuota

- venta;
- número;
- vencimiento;
- importe original.

### Recargo

- cuota;
- fecha;
- importe.

Una restricción impedirá crear dos recargos para la misma cuota y fecha.

### Pago

- cliente;
- venta;
- fecha;
- importe;
- método;
- observaciones;
- estado registrado/anulado;
- fecha y motivo de anulación.

### Aplicación de pago

- pago;
- cuota;
- componente capital/recargo;
- importe aplicado.

### Intento de cobranza

- cliente;
- venta;
- fecha;
- resultado: no pagó, ausente, prometió pagar u otro;
- observaciones.

## 6. Reglas financieras iniciales

Para poder terminar en 2–3 días se usarán inicialmente estas reglas:

1. El recargo comienza al día siguiente del vencimiento.
2. Se aplica por cuota y por día calendario.
3. Continúa mientras quede saldo.
4. Un pago se aplica a la cuota más antigua.
5. Dentro de la cuota se pagan primero recargos y después capital.
6. Un pago no puede superar la deuda exigible seleccionada.
7. Los atrasados aparecen todos los días.
8. “No pagó” no cambia el saldo.
9. El recargo configurado se copia a la venta.
10. Cambiar la configuración no modifica ventas anteriores.
11. Los pagos se anulan, no se borran.
12. La última cuota absorbe diferencias de centavos.

Estas reglas podrán cambiarse antes de implementar el motor de cobranza.

## 7. Backup y exportación

### 7.1 Backup correcto

El backup principal será una copia SQLite comprimida:

```text
backups/gestion_2026-07-24_183000.sqlite3.zip
```

Es la mejor opción porque conserva:

- tablas;
- relaciones;
- identificadores;
- cuotas;
- pagos;
- asignaciones;
- configuración;
- integridad de los datos.

La copia se realizará con la API de backup de SQLite, no copiando un archivo
que podría estar siendo escrito. Después se comprimirá y validará
automáticamente antes de publicarse.

### 7.2 Cuándo se respalda

- al iniciar, si no existe una copia reciente;
- después de una operación financiera importante, actualizando una copia de
  recuperación;
- al crear una copia manual desde “Datos y respaldo”;
- al presionar “Cerrar y respaldar”;
- antes de restaurar otra copia.

### 7.3 Retención

- conservar una copia de cierre por día durante 90 días;
- conservar una copia de recuperación reciente;
- no borrar automáticamente exportaciones del usuario;
- mostrar fecha y tamaño del último backup.

### 7.4 Exportación CSV

CSV no será el backup principal porque una sola hoja no representa bien las
relaciones. El botón “Exportar datos” generará un ZIP:

```text
export_2026-07-24_183000.zip
|-- clientes.csv
|-- productos.csv
|-- ventas.csv
|-- cuotas.csv
|-- recargos.csv
|-- pagos.csv
|-- aplicaciones_pago.csv
|-- intentos_cobranza.csv
|-- configuracion.csv
`-- resumen.txt
```

Los CSV usarán UTF-8 con BOM para abrir correctamente en Excel y conservarán
importes sin símbolos monetarios.

### 7.5 Restauración

La restauración se hará con el programa cerrado:

1. detectar y preseleccionar la copia válida más reciente;
2. permitir elegir otra copia solo si se necesita;
3. validar y descomprimir automáticamente el ZIP;
4. crear backup preventivo de la base actual;
5. validar que la copia sea una base SQLite válida;
6. reemplazar la base;
7. ejecutar comprobación de integridad;
8. abrir el sistema automáticamente.

## 8. WhatsApp opcional simple

No se usará API ni envío automático. En el historial o cobranza aparecerá:

```text
[ Abrir WhatsApp ]
```

El botón abrirá una URL `wa.me` con un texto precargado, por ejemplo:

```text
Hola Juan. Te recordamos que hoy tenés una cuota pendiente de $25.000.
```

La persona revisará el mensaje y presionará Enviar manualmente. Esto evita:

- alta en Meta Business;
- plantillas;
- costos;
- tareas automáticas;
- riesgo de mensajes duplicados.

## 9. Plan de trabajo de 2–3 días

### Paso 0. Cerrar cinco reglas — 30 a 60 minutos

Confirmar:

1. si domingos generan recargo;
2. si el pago parcial continúa generando recargo;
3. si se permiten pagos adelantados;
4. qué significa cancelar una venta;
5. si existen datos anteriores para importar.

Resultado:

- reglas suficientes para programar sin detenerse.

### Paso 1. Base local portable — 2 a 3 horas

Acciones:

1. Crear proyecto Django.
2. Configurar SQLite en `data/`.
3. Crear carpetas de datos, backups, exportaciones y media.
4. Configurar español, ARS y Buenos Aires.
5. Añadir archivos estáticos locales.
6. Crear launcher.
7. Crear acceso de inicio.
8. Crear página base y navegación.
9. Añadir pruebas básicas.
10. Comprobar que no necesita Internet.

Aceptación:

- doble clic abre la página local;
- la base se crea fuera del código;
- cerrar desde el launcher detiene el servidor.

### Paso 2. Modelos y configuración — 2 a 3 horas

Acciones:

1. Crear modelos de la sección 5.
2. Crear migraciones.
3. Crear restricciones.
4. Crear configuración única.
5. Crear datos predeterminados.
6. Crear servicio de saldos.
7. Crear servicio de recargos idempotentes.

Aceptación:

- la base puede reconstruirse con migraciones;
- no existen recargos duplicados;
- importes usan decimal exacto.

### Paso 3. Clientes, productos y ventas — 4 a 6 horas

Acciones:

1. Lista y búsqueda de clientes.
2. Alta y edición.
3. Archivado.
4. Historial vacío inicial.
5. Productos.
6. Formulario de venta.
7. Previsualización del cronograma.
8. Creación de cuotas.
9. Detalle de venta.
10. Estados de venta.

Aceptación:

- una venta de $480.000 genera 12 cuotas de $40.000;
- las fechas semanales y quincenales son correctas;
- el total de cuotas coincide con la venta.

### Paso 4. Cobranza y pagos — 5 a 7 horas

Acciones:

1. Aplicar recargos faltantes al abrir.
2. Mostrar deuda de hoy.
3. Mostrar atrasados.
4. Mostrar dirección y producto.
5. Registrar pago.
6. Registrar pago parcial.
7. Aplicar pago a deuda antigua.
8. Calcular saldo.
9. Anular pago.
10. Registrar “No pagó”.
11. Añadir enlace de WhatsApp opcional.

Aceptación:

- los ejemplos de $20.000 + $5.000 diarios funcionan;
- el saldo parcial se recuerda;
- no puede guardarse dos veces el mismo pago por doble clic.

### Paso 5. Dashboard, semana e historial — 3 a 4 horas

Acciones:

1. Dashboard.
2. Clientes a cobrar.
3. Monto esperado.
4. Clientes atrasados.
5. Total adeudado.
6. Cobrado hoy.
7. Vista simultánea de lunes a sábado con acceso a la cobranza diaria.
8. Accesos lunes a sábado.
9. Historial del cliente.
10. Historial de venta, cuotas y pagos.

Aceptación:

- los totales coinciden con los detalles;
- elegir una fecha abre correctamente la semana que la contiene.

### Paso 6. Impresión y reportes — 3 a 4 horas

Acciones:

1. Crear planilla A4.
2. Añadir firma y observaciones.
3. Añadir logo.
4. Probar impresión.
5. Cobrado hoy/semana/mes.
6. Morosos.
7. Clientes al día.
8. Total pendiente.
9. Productos más vendidos.
10. Clientes con mayor deuda.

Aceptación:

- se imprime correctamente en A4;
- los reportes coinciden con pagos y saldos.

### Paso 7. Backup, exportación y cierre — 3 a 4 horas

Acciones:

1. Implementar API de backup SQLite.
2. Crear copia de recuperación.
3. Crear el backup manual dentro de “Datos y respaldo”.
4. Crear “Cerrar y respaldar”.
5. Rotar copias.
6. Exportar ZIP de CSV.
7. Crear restaurador externo.
8. Probar restauración completa.

Aceptación:

- cerrar crea una copia;
- restaurar recupera clientes, ventas, cuotas y pagos;
- el ZIP abre correctamente en Excel.

### Paso 8. Pruebas y paquete portable — 4 a 6 horas

Acciones:

1. Probar casos financieros.
2. Probar nombres y direcciones largos.
3. Probar varios días.
4. Probar apagado inesperado.
5. Probar backup y restore.
6. Probar sin Internet.
7. Construir paquete PyInstaller.
8. Copiar a otra carpeta.
9. Abrir la copia portable.
10. Escribir manual de una página.

Aceptación:

- el paquete abre sin instalar Python;
- los datos permanecen fuera del ejecutable;
- una copia de respaldo se puede restaurar.

## 10. Orden diario sugerido

### Día 1

- Pasos 0–3.
- Resultado: clientes, productos, ventas y cuotas.

### Día 2

- Pasos 4–6.
- Resultado: cobranza completa, semana, historial, planilla y reportes.

### Día 3

- Pasos 7–8.
- Resultado: backups, CSV, restauración, pruebas y paquete portable.

Es un cronograma exigente pero viable para un MVP local porque se eliminan
infraestructura, usuarios, nube e integraciones automáticas. Correcciones
visuales o importaciones complejas podrían extenderse después sin impedir el
uso.

## 11. Casos de prueba obligatorios

1. Cliente con y sin DNI.
2. Venta semanal.
3. Venta quincenal.
4. Redondeo de última cuota.
5. Pago en término.
6. Uno, dos y tres días de atraso.
7. Pago parcial.
8. Nuevo recargo después de pago parcial.
9. Dos cuotas vencidas.
10. Dos ventas del cliente.
11. Pago anulado.
12. “No pagó”.
13. Cambio de recargo para ventas nuevas.
14. Consulta de lunes a sábado.
15. PDF/impresión con 18 clientes.
16. Exportación CSV.
17. Backup.
18. Restauración.
19. Ejecución sin Internet.
20. Copia portable en otra carpeta.

## 12. Definición de terminado

El MVP estará terminado cuando:

- abra con doble clic;
- funcione sin Internet;
- permita todo el flujo cliente–venta–cuota–pago;
- calcule recargos y pagos parciales;
- muestre cobranza y semana;
- imprima A4;
- muestre reportes;
- cree backup al cerrar;
- exporte CSV;
- restaure una copia;
- funcione desde una carpeta portable;
- pase los 20 casos obligatorios.

## 13. Estado final y evolución opcional

El MVP terminó las ocho fases. El siguiente paso no es otra fase obligatoria,
sino usar una copia portable con datos reales durante algunos días y registrar
ajustes de comodidad.

Mejoras opcionales posteriores:

- importación asistida desde planillas anteriores;
- instalador o acceso directo con icono;
- firma digital de los ejecutables;
- gráficos adicionales;
- recordatorios de WhatsApp más elaborados;
- sincronización externa de backups elegida por el usuario.
