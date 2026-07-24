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
- crear un backup SQLite manual;
- descargar cualquier backup conservado;
- exportar todos los datos en un ZIP de CSV;
- volver a descargar exportaciones anteriores;
- consultar las instrucciones para restaurar.

## 2. Copias SQLite restaurables

Una copia SQLite conserva en un único archivo:

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

Cada copia se valida con `PRAGMA quick_check` antes de publicarse. La escritura
se realiza primero en un archivo temporal y después se reemplaza atómicamente.

### Copias automáticas

| Tipo | Momento | Retención |
| --- | --- | ---: |
| Inicio | Al abrir el programa | 5 |
| Antes de actualizar | Antes de aplicar migraciones | 5 |
| Recuperación | Al iniciar y después de cada alta o cambio importante | 1 fija |
| Cierre | Al usar “Cerrar y respaldar” | 30 |
| Preventiva | Antes de una restauración | 10 |

Las copias manuales conservan las 30 más recientes.

La copia fija:

```text
backups\gestion_recovery.sqlite3
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
`.sqlite3`.

## 4. Restaurador externo

La base no debe reemplazarse mientras Django la está utilizando. Por eso la
restauración se realiza con una herramienta externa:

```text
scripts\Restaurar.bat
```

### Procedimiento para restaurar

1. En la ventana pequeña del programa, presionar “Cerrar y respaldar”.
2. Esperar a que se cierre por completo.
3. Hacer doble clic en `scripts\Restaurar.bat`.
4. Presionar “Seleccionar backup…”.
5. Elegir un archivo `.sqlite3`.
6. Confirmar “Restaurar copia seleccionada”.
7. Esperar el mensaje “Datos restaurados”.
8. Abrir otra vez con `scripts\Iniciar.bat`.
9. Comprobar clientes, ventas y cobranza.

El restaurador:

1. detecta si el servidor local sigue abierto;
2. comprueba que el archivo sea SQLite íntegro;
3. comprueba que contenga tablas propias de Gestión Financiera;
4. prepara una copia temporal validada;
5. crea un backup preventivo de la base actual;
6. reemplaza la base;
7. vuelve a comprobar la integridad.

Si la copia seleccionada no es válida, la base activa no se modifica.

## 5. Ubicación y portabilidad

Los datos siguen separados del código:

```text
data\gestion_financiera.sqlite3
backups\gestion_*.sqlite3
exports\export_*.zip
media\
```

Para trasladar todo el uso a otra carpeta o equipo durante el desarrollo,
conviene copiar juntas las carpetas `data`, `backups`, `exports` y `media`.
La Fase 8 construirá el paquete que no requerirá tener Python instalado.

## 6. Pruebas cubiertas

La suite verifica:

- integridad y rotación de backups;
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
108 pruebas aprobadas
```

## 7. Criterios de aceptación

- “Cerrar y respaldar” crea una copia final: cumplido.
- Existe una copia reciente después de operaciones importantes: cumplido.
- Un backup puede descargarse desde la aplicación: cumplido.
- La exportación genera CSV legibles por Excel: cumplido.
- Restaurar recupera datos y conserva primero la base anterior: cumplido.
- La restauración solo se ejecuta con la aplicación cerrada: cumplido.

