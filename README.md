# Gestión Financiera

Aplicación local y monousuario para administrar clientes, ventas financiadas,
cuotas, recargos y cobranzas.

Estado actual: Fases 0, 1 y 2 terminadas. La base local, las reglas financieras,
los modelos relacionales, los cronogramas de cuotas, los saldos y los recargos
idempotentes están operativos. Próximo paso: clientes, productos y ventas.

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
- crea un backup de inicio;
- abre `http://127.0.0.1:8765/`;
- muestra una pequeña ventana de control;
- permite abrir el navegador, crear un backup o cerrar y respaldar.

Para ejecutar el servidor de desarrollo con consola:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\Desarrollo.ps1
```

Para ejecutar controles y pruebas:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\Probar.ps1
```

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
- [Auditoría del equipo](docs/ENTORNO_Y_PORTABILIDAD.md).
- [Plan empresarial anterior, conservado como referencia](docs/PLAN_MAESTRO.md).
