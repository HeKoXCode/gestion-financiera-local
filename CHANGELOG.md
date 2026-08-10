# Changelog

Los cambios relevantes de Gestión Financiera se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto utiliza [versionado semántico](https://semver.org/lang/es/).

## [Unreleased]

### Added

- Flujo integrado de préstamos con capital, interés total y medio de entrega.
- Estado de cuenta del cliente en PDF, impresión y opción de compartir.
- Acceso temporal desde celular mediante token de sesión y red local.
- Paquete de actualización que conserva datos, respaldos, exportaciones y archivos del usuario.
- Evidencia visual generada con una base completamente ficticia.
- Validación continua de lint, Django, migraciones, pruebas y cobertura.

### Changed

- README preparado para publicación pública y distribución mediante GitHub Releases.
- Versión del proyecto alineada a `1.0.0`.
- Documentación histórica separada del plan vigente.

### Security

- Bases, claves locales, respaldos, exportaciones, outputs y paquetes portables permanecen fuera de Git.
- El acceso móvil se mantiene deshabilitado por defecto y utiliza un token aleatorio por ejecución.
