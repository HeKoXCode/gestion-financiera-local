# Gestión Financiera v1.1.0

Esta versión cierra GF-C1 y GF-C2 sin retirar el modo portable local de `v1.0.0`.

## Destacado

- perfil multiusuario optativo con roles, PostgreSQL y HTTPS;
- auditoría append-only y backups externos verificados;
- dashboard de aging, recuperación, comportamiento y cohortes;
- data mart CSV listo para Power BI y sin identificadores directos;
- 225 pruebas, 88% de cobertura combinada y dos jobs de CI: Windows y configuración cloud Linux.

## Compatibilidad

El portable continúa iniciando en modo local con SQLite y sin login. Las funciones multiusuario sólo se activan mediante variables de entorno y el despliegue documentado en `deploy/`.

## Seguridad

No subas `deploy/.env`. Las contraseñas se leen desde variables de entorno. Antes de publicar un servicio compartido, ejecutá `manage.py check --deploy`, creá un backup externo y probá su restauración.
