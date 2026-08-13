# Gestión Financiera Local v1.0.0

Primera release pública portable para Windows de Gestión Financiera Local.

## Incluye

- gestión de clientes, productos, ventas financiadas y préstamos;
- cuotas semanales, quincenales y mensuales;
- pagos completos y parciales, anulaciones y recargos;
- cobranza diaria/semanal, historial y reportes;
- estados de cuenta PDF y exportaciones CSV;
- backup, restauración y archivo/reinicio;
- acceso temporal opcional desde celular en la red local.

## Verificación

La release se publica con:

- ZIP portable versionado;
- `SHA256SUMS.txt`;
- reporte JSON de auditoría;
- prueba desde una extracción aislada sin Python externo;
- análisis local con Microsoft Defender;
- CI con lint, Django checks, migraciones, pytest y cobertura mínima del 85%.

## Firma y SmartScreen

Los ejecutables de `v1.0.0` no tienen firma Authenticode. Windows puede mostrar “Editor desconocido”. Descargá el paquete solamente desde este repositorio, verificá el SHA-256 publicado y no desactives Microsoft Defender.

## Datos

El ZIP comienza sin clientes, ventas ni información privada. `data/`, backups, exportaciones, archivos cargados y claves locales no forman parte de la release.

## Alcance

Aplicación gratuita, local y monousuario. No incluye sincronización cloud, acceso público por Internet ni reemplaza un sistema contable, fiscal o bancario.
