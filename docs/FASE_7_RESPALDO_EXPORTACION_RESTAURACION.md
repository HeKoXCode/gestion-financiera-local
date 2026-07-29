# Fase 7: respaldo, exportación y restauración

Estado: terminada  
Fecha: 24/07/2026

## Objetivo

Proteger los datos del programa sin depender de Internet, permitir su consulta
en Excel y ofrecer una restauración segura que no requiera manipular archivos a
mano.

## 1. Pantalla “Datos y respaldo”

La navegación principal incorpora la pantalla:

```text
Datos y respaldo
```

Desde allí se puede:

- comprobar si existe la base activa;
- consultar la fecha de la copia de recuperación;
- crear un backup SQLite comprimido manual;
- descargar cualquier backup conservado;
- exportar todos los datos en un ZIP de CSV;
- volver a descargar exportaciones anteriores;
- consultar las instrucciones para restaurar.

## 2. Copias SQLite comprimidas y restaurables

Una copia `.sqlite3.zip` conserva en un único archivo:

- clientes y productos;
- ventas y cuotas;
- recargos;
- pagos y sus aplicaciones;
- intentos de cobranza;
- configuración general;
- relaciones e identificadores internos.

La copia se crea con la API de backup de SQLite. Esto permite obtener una
imagen consistente aunque la aplicación haya tenido actividad y evita copiar
un archivo a mitad de una escritura.

Cada copia se valida con `PRAGMA quick_check`, se comprime en ZIP y se vuelve a
leer por completo para comprobar su estructura y CRC antes de publicarse. La
escritura se realiza primero en archivos temporales y después se reemplaza
atómicamente.

Al iniciar, las copias antiguas `.sqlite3` válidas se convierten
automáticamente a `.sqlite3.zip`. El archivo anterior solo se elimina después
de validar la copia comprimida. Los `.sqlite3` también continúan siendo
aceptados por el restaurador para conservar compatibilidad.

### Copias automáticas

| Tipo | Momento | Retención |
| --- | --- | ---: |
| Inicio | Al abrir el programa | 5 |
| Antes de actualizar | Antes de aplicar migraciones | 5 |
| Recuperación | Al iniciar y después de cada alta o cambio importante | 1 fija |
| Cierre | Al usar “Cerrar y crear respaldo” | 1 por día, 90 días |
| Preventiva | Antes de una restauración | 10 |

Las copias manuales conservan las 30 más recientes. Si el programa se cierra
varias veces durante el mismo día, la copia de cierre de esa fecha se actualiza
en lugar de crear archivos repetidos.

La copia fija:

```text
backups\gestion_recovery.sqlite3.zip
```

se actualiza después de guardar configuración, clientes, productos, ventas,
pagos, anulaciones y resultados de visitas. Un error al actualizar esta copia
se registra, pero no revierte una operación que ya fue guardada correctamente.

## 3. Exportación ZIP/CSV

El botón “Descargar ZIP de CSV” genera y conserva un archivo como:

```text
exports\export_2026-07-24_183000_123456.zip
```

Su contenido es:

```text
clientes.csv
productos.csv
ventas.csv
cuotas.csv
recargos.csv
pagos.csv
aplicaciones_pago.csv
intentos_cobranza.csv
configuracion.csv
resumen.txt
```

Características:

- codificación UTF-8 con BOM para reconocer tildes y eñes en Excel;
- punto y coma como separador, adecuado para la configuración regional
  argentina;
- salto de línea compatible con Windows;
- importes decimales con punto y sin símbolo monetario;
- columnas `*_id` para conservar las relaciones entre archivos;
- protección de textos que podrían interpretarse como fórmulas;
- validación del ZIP antes de ofrecer la descarga;
- las exportaciones no se eliminan automáticamente.

El ZIP sirve para consultar, filtrar o analizar datos. No es el medio de
restauración porque varios CSV no reconstruyen automáticamente todas las
relaciones y restricciones. Para recuperar el programa se usa un backup
`.sqlite3.zip`.

## 4. Restaurador externo

La base no debe reemplazarse mientras Django la está utilizando. Por eso la
restauración se realiza con una herramienta externa:

```text
scripts\Restaurar.bat
```

### Procedimiento normal para restaurar

1. En el panel de inicio, presionar “Cerrar y crear respaldo”.
2. Esperar a que se cierre por completo.
3. Hacer doble clic en `scripts\Restaurar.bat`.
4. Revisar la copia más reciente seleccionada automáticamente.
5. Presionar “Restaurar la copia mostrada” y confirmar.
6. Esperar el mensaje “Datos restaurados”.
7. El programa volverá a abrirse automáticamente.
8. Comprobar clientes, ventas y cobranza.

“Elegir otra copia…” permite recuperar una fecha anterior o seleccionar un
archivo guardado en otro disco. No hay que abrir ni descomprimir el ZIP a mano.

El restaurador:

1. detecta si el servidor local sigue abierto;
2. localiza y preselecciona la copia válida más reciente;
3. comprueba la estructura y el CRC del ZIP;
4. descomprime la base en una ubicación temporal controlada;
5. comprueba que sea SQLite íntegro y contenga las tablas del programa;
6. crea un backup preventivo comprimido de la base actual;
7. reemplaza la base;
8. vuelve a comprobar la integridad;
9. abre nuevamente Gestión Financiera.

Si la copia seleccionada no es válida, la base activa no se modifica.

## 5. Ubicación y portabilidad

Los datos siguen separados del código:

```text
data\gestion_financiera.sqlite3
backups\gestion_*.sqlite3.zip
exports\export_*.zip
media\
```

Para trasladar todo el uso a otra carpeta o equipo durante el desarrollo,
conviene copiar juntas las carpetas `data`, `backups`, `exports` y `media`.
La Fase 8 construirá el paquete que no requerirá tener Python instalado.

## 6. Pruebas cubiertas

La suite verifica:

- integridad y rotación de backups;
- compresión y lectura completa de los ZIP;
- conversión segura de backups `.sqlite3` anteriores;
- rechazo de ZIP dañados o con rutas internas inseguras;
- catálogo y descarga segura de copias;
- rechazo de rutas manipuladas;
- rechazo de archivos que no pertenecen al programa;
- restauración completa sobre archivos temporales;
- conservación preventiva de la base anterior;
- ZIP con todos los CSV esperados;
- codificación UTF-8 con BOM;
- separador compatible con Excel;
- importes y caracteres acentuados;
- relaciones por identificadores;
- protección ante fórmulas en celdas;
- generación, catálogo y descarga de exportaciones;
- actualización de la copia fija de recuperación;
- pantalla de administración de datos.

Resultado al cerrar la fase:

```text
120 pruebas aprobadas
```

## 7. Criterios de aceptación

- “Cerrar y crear respaldo” crea una copia final: cumplido.
- Existe una copia reciente después de operaciones importantes: cumplido.
- Un backup puede descargarse desde la aplicación: cumplido.
- La exportación genera CSV legibles por Excel: cumplido.
- Restaurar recupera datos y conserva primero la base anterior: cumplido.
- La restauración solo se ejecuta con la aplicación cerrada: cumplido.
