# Fase 1: base local portable

Estado: completada.

## Decisiones aplicadas

- Aplicación local monousuario.
- Sin autenticación.
- Servidor enlazado solamente a `127.0.0.1`.
- Django 5.2.16.
- Python 3.12.
- SQLite con claves foráneas, WAL y espera de bloqueo.
- Datos externos al código.
- Dependencias bloqueadas con hashes.
- Interfaz y recursos locales.
- Lanzador con ventana de control.
- Backup mediante la API de SQLite.

## Componentes creados

- Proyecto Django.
- Módulo `core`.
- Página inicial de estado.
- Endpoint `/health/`.
- Configuración española y zona horaria de Buenos Aires.
- Base en `data/gestion_financiera.sqlite3`.
- Generación persistente de clave local.
- Lanzador en `launcher/launcher.py`.
- Backup validado en `launcher/backup.py`.
- Scripts de instalación, inicio, desarrollo y pruebas.
- Archivos de bloqueo de dependencias.
- Pruebas de salud, configuración y backup.

## Controles ejecutados

```text
[x] Ruff
[x] Django system check
[x] Migraciones SQLite
[x] Endpoint de salud real
[x] Backup real
[x] Validación de integridad SQLite
[x] Rotación de backups
[x] 9 pruebas automáticas
[x] Cobertura total superior al mínimo
```

Resultado de pruebas al cerrar la fase:

```text
9 passed
83% coverage
0 errores de Ruff
0 errores de Django check
```

## Forma de iniciar

```text
scripts\Iniciar.bat
```

El primer inicio prepara el entorno si todavía no existe. Los siguientes
inicios utilizan el entorno ya instalado.

## Alcance pendiente

La fase 1 no contiene todavía:

- clientes;
- productos;
- ventas;
- cuotas;
- pagos;
- recargos;
- agenda;
- reportes;
- CSV;
- paquete `.exe`.

Esas funciones se construirán sobre esta base durante los pasos siguientes del
plan local.

