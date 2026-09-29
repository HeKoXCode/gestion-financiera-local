# Gestión Financiera v1.8.0

La versión 1.8.0 reúne la edición local 1.7.2 y la edición técnica publicada
previamente en GitHub. El resultado conserva el portable completo para Windows
y suma un perfil multiusuario administrado.

## Novedades principales

- Préstamos integrados con cuotas, cobranza, recorridos y reportes.
- Cobradores, planillas, pagos adelantados y recargo único diario.
- Archivo seguro y correcciones con versiones anteriores inmutables.
- Analítica de cartera, aging, cohortes y recuperación con conciliaciones.
- Data mart seudonimizado para Power BI.
- Login, roles y auditoría para el perfil multiusuario.
- PostgreSQL, Docker Compose, Caddy HTTPS y backups verificados.
- Demo ficticia aislada, reversible y sin límites de clientes.

## Qué descargar

- `GestionFinanciera-v1.8.0-windows-x64.zip`: instalación portable completa.
- `GestionFinanciera-actualizacion-1.8.0.zip`: archivos de aplicación sin datos.
- `SHA256SUMS.txt`: hashes para comprobar integridad.
- `release-audit-v1.8.0.json` y `release-audit-update-v1.8.0.json`: evidencia
  automatizada del control de distribución.

## Actualización segura

1. Cerrá Gestión Financiera normalmente.
2. Confirmá que existe una copia reciente en `backups/`.
3. Probá primero sobre una copia de la instalación.
4. Aplicá únicamente el ZIP de actualización.
5. No reemplaces `data/`, `backups/`, `exports/`, `media/` ni `storage/`.
6. Abrí la aplicación y comprobá clientes, operaciones, cobranzas y reportes.

## Alcance

La edición es gratuita y completa bajo MIT. El portable está pensado para una
instalación local. El perfil multiusuario requiere administración de servidor,
dominio, secretos, backups y actualizaciones. No existe sincronización offline
entre instalaciones y la aplicación no reemplaza sistemas contables, fiscales
o bancarios.
