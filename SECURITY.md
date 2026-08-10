# Política de seguridad

## Alcance soportado

Las correcciones de seguridad se aplican sobre la versión más reciente de la rama principal. La aplicación está diseñada para ejecución local y no debe exponerse directamente a Internet.

## Reportar una vulnerabilidad

Cuando el repositorio esté publicado, utilizar el reporte privado de vulnerabilidades de GitHub si está habilitado. No incluir claves, bases de datos, respaldos ni información de clientes en un issue público.

El reporte debería indicar:

- componente y versión afectada;
- pasos mínimos para reproducir el problema con datos ficticios;
- impacto esperado;
- mitigación conocida, si existe.

## Datos sensibles

Nunca deben incluirse en Git:

- `data/` y su `.secret_key`;
- bases SQLite;
- `backups/`, `exports/`, `storage/` y `media/`;
- variables de entorno o tokens de acceso móvil;
- paquetes portables generados con datos reales.

Antes de publicar un release se debe probar el ZIP en una carpeta aislada, verificar que inicia sin datos reales y publicar su hash SHA-256.
