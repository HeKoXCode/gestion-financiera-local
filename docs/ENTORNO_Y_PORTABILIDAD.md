# Entorno objetivo y estrategia de portabilidad

Fecha de revisión: 10 de agosto de 2026.

## Decisión vigente

Gestión Financiera se distribuye como una aplicación local y monousuario para Windows. La implementación utiliza:

- Python 3.12 durante el desarrollo;
- Django 5.2 y SQLite;
- servidor local en `127.0.0.1` por defecto;
- HTML, CSS y JavaScript incluidos en el paquete;
- PyInstaller en modo carpeta;
- datos, respaldos, exportaciones y archivos multimedia fuera del ejecutable;
- ejecutables separados para la aplicación, restauración y archivado;
- funcionamiento diario sin Docker, PostgreSQL, Node.js ni Python instalado.

Esta decisión reemplaza la arquitectura empresarial exploratoria conservada en [archive/PLAN_MAESTRO.md](archive/PLAN_MAESTRO.md).

## Entorno soportado

| Uso | Requisito |
|---|---|
| Desarrollo | Windows 11 y Python `>=3.12,<3.13` |
| Instalación portable | Windows 10/11 de 64 bits |
| Persistencia | SQLite local |
| Navegador | Navegador moderno incluido en Windows |
| Red | No requerida, salvo acceso temporal desde otro dispositivo de la LAN |

Las características específicas del equipo de desarrollo no forman parte de los requisitos del producto.

## Principios de portabilidad

- No guardar rutas absolutas del equipo de desarrollo.
- Resolver rutas con `pathlib` y variables de entorno.
- Mantener `data/`, `backups/`, `exports/`, `storage/` y `media/` fuera del ejecutable.
- Fijar dependencias mediante archivos lock.
- No incluir claves, tokens, bases ni respaldos en Git o en paquetes limpios.
- Construir y probar el portable desde una copia aislada.
- Conservar un manifiesto de integridad de los archivos distribuidos.

## Variables de directorio

El desarrollo y las pruebas pueden aislar su estado mediante:

- `GESTION_DATA_DIR`;
- `GESTION_BACKUP_DIR`;
- `GESTION_EXPORT_DIR`;
- `GESTION_MEDIA_DIR`.

Esto permite ejecutar demos y QA sin tocar la instalación real.

## Construcción

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ConstruirPortable.ps1
```

El proceso debe:

1. ejecutar los controles automáticos;
2. generar los ejecutables;
3. copiar únicamente recursos necesarios;
4. iniciar una copia aislada;
5. comprobar rutas y recursos visuales;
6. generar el manifiesto y el ZIP.

## Verificación previa a una publicación

- El paquete inicia sin datos reales.
- No contiene `.secret_key`, bases, respaldos ni exportaciones.
- Las migraciones se aplican en una carpeta limpia.
- Backup y restauración funcionan sobre datos ficticios.
- El acceso móvil permanece desactivado por defecto.
- El ZIP publicado incluye hash SHA-256 y notas de versión.

La evidencia funcional detallada está en [FASE_8_PRUEBAS_Y_PAQUETE_PORTABLE.md](FASE_8_PRUEBAS_Y_PAQUETE_PORTABLE.md) y [FASE_FINAL_3_QA.md](FASE_FINAL_3_QA.md).
