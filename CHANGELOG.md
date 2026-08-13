# Changelog

Los cambios relevantes de Gestión Financiera se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto utiliza [versionado semántico](https://semver.org/lang/es/).

## [Unreleased]

## [1.0.0] - 2026-08-13

### Added

- Flujo integrado de préstamos con capital, interés total y medio de entrega.
- Estado de cuenta del cliente en PDF, impresión y opción de compartir.
- Acceso temporal desde celular mediante token de sesión y red local.
- Paquete de actualización que conserva datos, respaldos, exportaciones y archivos del usuario.
- Evidencia visual generada con una base completamente ficticia.
- Validación continua de lint, Django, migraciones, pruebas y cobertura.
- ZIP portable versionado, checksum SHA-256 y auditoría desde extracción aislada.
- Workflow de prueba de release para tags y ejecuciones manuales.
- GIF reproducible del recorrido operación → cuotas/pagos → cobranza → reportes.

### Changed

- README preparado para publicación pública y distribución mediante GitHub Releases.
- Versión del proyecto alineada a `1.0.0`.
- Documentación histórica separada del plan vigente.
- Documentación de cierre GF-I1 a GF-I4 y modelo de datos simplificado.

### Security

- Bases, claves locales, respaldos, exportaciones, outputs y paquetes portables permanecen fuera de Git.
- El acceso móvil se mantiene deshabilitado por defecto y utiliza un token aleatorio por ejecución.
- El ZIP final se rechaza si contiene bases, claves, backups, exportaciones o rutas inseguras.
- La decisión de distribuir `v1.0.0` sin firma Authenticode queda explícita junto con la verificación por SHA-256 y Microsoft Defender.

[Unreleased]: https://github.com/HeKoXCode/gestion-financiera-local/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/HeKoXCode/gestion-financiera-local/releases/tag/v1.0.0
