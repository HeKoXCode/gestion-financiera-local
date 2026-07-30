# Gestión Financiera

Aplicación local y monousuario para administrar clientes, ventas financiadas,
cuotas, recargos y cobranzas.

Estado actual: Fases 0 a 8 terminadas. El MVP está terminado y permite administrar
clientes, productos y ventas; generar cuotas y recargos; consultar la cobranza;
registrar pagos completos o parciales; anularlos; conservar las visitas; revisar
el resumen diario, comparar la carga semanal, consultar el historial completo,
imprimir la planilla A4, analizar reportes de cobranza y saldos, crear y
descargar copias de seguridad, exportar CSV y restaurar una copia de forma segura.

La entrega portable validada se encuentra en:

```text
portable\GestionFinanciera\
portable\GestionFinanciera-portable.zip
```

Para utilizarla no es necesario instalar Python, Docker ni PostgreSQL.

La aplicación se ejecutará localmente con Python/Django y SQLite. La versión
final se entregará como una carpeta portable que podrá abrirse mediante acceso
directo, sin necesitar PostgreSQL, Docker ni conexión a Internet.

## Inicio rápido de desarrollo

La primera vez:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\InstalarDesarrollo.ps1
```

Después, hacer doble clic en:

```text
scripts\Iniciar.bat
```

El lanzador:

- aplica migraciones pendientes;
- actualiza los recargos diarios faltantes;
- crea una copia de seguridad al iniciar;
- muestra una ventana de inicio clara, sin abrir el navegador automáticamente;
- permite entrar al sistema con “Abrir sistema”;
- permite cerrar de forma segura y crear el respaldo final.

La sección “Datos y respaldo” del menú permite crear y descargar copias
comprimidas (`.sqlite3.zip`) y exportar un ZIP con archivos CSV compatible con
Excel. Al cerrar se actualiza una sola copia por día y se conservan hasta 90
días de cierres.

Para restaurar una copia, primero cerrar el sistema y hacer doble clic en:

```text
scripts\Restaurar.bat
```

El restaurador selecciona automáticamente la copia válida más reciente, valida
y descomprime el ZIP, y crea una copia preventiva antes de reemplazar los datos.
Después vuelve a abrir el sistema. También admite copias `.sqlite3` anteriores.

Para guardar la base completa con un nombre reconocible y comenzar otra desde
cero, cerrar primero el sistema y hacer doble clic en:

```text
scripts\ArchivarYReiniciar.bat
```

La herramienta pide un nombre y una confirmación. Crea en `storage/` un archivo
`.sqlite3.zip` con ese nombre y la fecha, comprueba que sea restaurable y recién
entonces deja vacía la base activa. Ese archivo puede recuperarse más adelante
con `scripts\Restaurar.bat`, usando “Elegir otra copia…”. No elimina los archivos
históricos guardados en `storage/`.

Para ejecutar el servidor de desarrollo con consola:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\Desarrollo.ps1
```

Para ejecutar controles y pruebas:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\Probar.ps1
```

## Paquete portable

Para construir nuevamente la entrega:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\ConstruirPortable.ps1
```

El proceso ejecuta las pruebas, genera los dos ejecutables, prueba una copia
aislada, crea un manifiesto de integridad y produce el ZIP.

La carpeta portable comienza sin datos reales. Para trasladar una base
existente, cerrá el sistema de origen, copiá una copia `.sqlite3.zip` a
`backups` del paquete y ejecutá `RESTAURAR_DATOS.bat`. El archivo aparecerá
seleccionado automáticamente si es la copia más reciente.

## Datos locales

```text
data/       Base SQLite y clave local
backups/    Copias de seguridad
exports/    Exportaciones CSV
storage/    Bases completas archivadas para retomarlas más adelante
media/      Logo y archivos cargados
```

Estas carpetas no se guardan en Git ni se mezclarán con el ejecutable.

## Requisitos durante el desarrollo

- Windows 11.
- Python 3.12.
- Internet solamente para la instalación inicial de dependencias.

Docker y PostgreSQL no son necesarios para este MVP.

Documentos:

- [Plan vigente del MVP local](docs/PLAN_MVP_LOCAL.md).
- [Reglas financieras de la Fase 0](docs/FASE_0_REGLAS_FINANCIERAS.md).
- [Base técnica implementada](docs/FASE_1_BASE_LOCAL.md).
- [Modelos y motor base de la Fase 2](docs/FASE_2_MODELOS_Y_MOTOR.md).
- [Interfaz y flujos de la Fase 3](docs/FASE_3_INTERFAZ_COMERCIAL.md).
- [Cobranza y pagos de la Fase 4](docs/FASE_4_COBRANZA_Y_PAGOS.md).
- [Resumen, semana e historial de la Fase 5](docs/FASE_5_DASHBOARD_AGENDA_HISTORIAL.md).
- [Impresión, reportes y configuración de la Fase 6](docs/FASE_6_IMPRESION_Y_REPORTES.md).
- [Respaldo, exportación y restauración de la Fase 7](docs/FASE_7_RESPALDO_EXPORTACION_RESTAURACION.md).
- [Pruebas y paquete portable de la Fase 8](docs/FASE_8_PRUEBAS_Y_PAQUETE_PORTABLE.md).
- [Auditoría y sistema de pulido visual final](docs/PULIDO_VISUAL_FINAL.md).
- [Revisión terminológica para Argentina](docs/REVISION_TERMINOLOGICA_AR.md).
- [Manual rápido incluido en la entrega](docs/MANUAL_USO_PORTABLE.txt).
- [Auditoría del equipo](docs/ENTORNO_Y_PORTABILIDAD.md).
- [Plan empresarial anterior, conservado como referencia](docs/PLAN_MAESTRO.md).
