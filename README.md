# Gestión Financiera

Aplicación local y monousuario para administrar clientes, ventas financiadas,
cuotas, recargos y cobranzas.

Estado actual: Fases 0 a 8 terminadas. El MVP está terminado y permite administrar
clientes, productos y ventas; generar cuotas y recargos; consultar la cobranza;
registrar pagos completos o parciales; anularlos; conservar las visitas; revisar
el dashboard, planificar la agenda semanal, consultar el historial consolidado,
imprimir la planilla A4, analizar reportes de cobranza y cartera, crear y
descargar backups, exportar CSV y restaurar una copia de forma segura.

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
- crea un backup de inicio;
- abre `http://127.0.0.1:8765/`;
- muestra una pequeña ventana de control;
- permite abrir el navegador o cerrar y respaldar.

La sección “Datos y respaldo” del menú permite crear y descargar backups
SQLite comprimidos (`.sqlite3.zip`) y exportar un ZIP de CSV compatible con
Excel. Al cerrar se actualiza una sola copia por día y se conservan hasta 90
días de cierres.

Para restaurar una copia, primero cerrar el programa y hacer doble clic en:

```text
scripts\Restaurar.bat
```

El restaurador selecciona automáticamente la copia válida más reciente, valida
y descomprime el ZIP, y crea un backup preventivo antes de reemplazar la base.
Después vuelve a abrir el programa. También admite copias `.sqlite3` anteriores.

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
existente, cerrá el programa de origen, copiá un backup `.sqlite3.zip` a
`backups` del paquete y ejecutá `RESTAURAR_DATOS.bat`. El archivo aparecerá
seleccionado automáticamente si es la copia más reciente.

## Datos locales

```text
data/       Base SQLite y clave local
backups/    Copias de seguridad
exports/    Exportaciones CSV
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
- [Dashboard, agenda e historial de la Fase 5](docs/FASE_5_DASHBOARD_AGENDA_HISTORIAL.md).
- [Impresión, reportes y configuración de la Fase 6](docs/FASE_6_IMPRESION_Y_REPORTES.md).
- [Respaldo, exportación y restauración de la Fase 7](docs/FASE_7_RESPALDO_EXPORTACION_RESTAURACION.md).
- [Pruebas y paquete portable de la Fase 8](docs/FASE_8_PRUEBAS_Y_PAQUETE_PORTABLE.md).
- [Manual rápido incluido en la entrega](docs/MANUAL_USO_PORTABLE.txt).
- [Auditoría del equipo](docs/ENTORNO_Y_PORTABILIDAD.md).
- [Plan empresarial anterior, conservado como referencia](docs/PLAN_MAESTRO.md).
