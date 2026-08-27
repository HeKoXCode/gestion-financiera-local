# Política de seguridad

## Alcance soportado

Las correcciones de seguridad se aplican sobre la versión más reciente de la rama principal. El portable local no debe exponerse a Internet. El perfil multiusuario sólo se admite detrás del proxy HTTPS documentado, con autenticación obligatoria y PostgreSQL.

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
- `deploy/.env`, contraseñas PostgreSQL y contraseñas de usuarios.

## Perfil multiusuario

La publicación compartida debe cumplir todos estos controles:

- `DJANGO_DEBUG=0`;
- `GESTION_AUTH_REQUIRED=1`;
- dominio explícito en `DJANGO_ALLOWED_HOSTS` y origen HTTPS confiable;
- Caddy u otro reverse proxy que establezca `X-Forwarded-Proto` de forma controlada;
- PostgreSQL, no SQLite compartido;
- contraseñas de al menos 12 caracteres y secretos fuera de Git;
- backup externo verificado y prueba periódica de restauración;
- revisión del registro de auditoría.

`python app/manage.py check --deploy --fail-level ERROR` rechaza una configuración multiusuario insegura.

Antes de publicar un release se debe probar el ZIP en una carpeta aislada, verificar que inicia sin datos reales y publicar su hash SHA-256.

## Firma y validación de releases

La versión `v1.0.0` se distribuye sin firma Authenticode porque el proyecto no dispone de un certificado de firma de código confiable. No se utiliza un certificado autofirmado. Windows puede mostrar “Editor desconocido”; esto no debe resolverse desactivando SmartScreen o Microsoft Defender.

Cada release pública debe incluir:

- ZIP descargado únicamente desde el repositorio oficial;
- `SHA256SUMS.txt` para verificar integridad;
- auditoría de rutas y contenido sensible;
- smoke test desde una extracción aislada;
- resultado de Microsoft Defender con cero detecciones.

El procedimiento y la decisión completa están documentados en [docs/I1_I4_RELEASE.md](docs/I1_I4_RELEASE.md).
