# 💳 Gestión Financiera Local

Aplicación gratuita, local y monousuario para administrar **clientes, ventas financiadas, préstamos, cuotas, recargos y cobranzas** sin depender de servicios en la nube.

> 🧭 **Posicionamiento:** proyecto de ingeniería de producto aplicada al dominio financiero.<br>
> 🔒 **Privacidad:** la base, los respaldos y las exportaciones permanecen en el equipo del usuario.<br>
> 🪟 **Entrega prevista:** aplicación portable para Windows, sin requerir Python en la PC de destino.

![Panel principal con datos ficticios](docs/assets/dashboard-demo.png)

## ✨ Qué problema resuelve

Gestión Financiera concentra el ciclo operativo de un negocio que vende o presta dinero en cuotas:

- registra clientes, productos, ventas y préstamos;
- genera calendarios semanales, quincenales o mensuales;
- calcula saldos y recargos con importes decimales;
- admite pagos completos, parciales y anulaciones trazables;
- prioriza la cobranza diaria y semanal;
- conserva el historial de cada cliente;
- produce reportes, planillas y estados de cuenta en PDF;
- crea, valida y restaura copias de seguridad;
- permite acceso temporal desde un celular dentro de la red local.

## 🖼️ Recorrido visual

Todas las capturas utilizan la base demo incluida; nombres, documentos, domicilios, teléfonos e importes son ficticios.

![Recorrido animado: operación, cuotas, cobranza y reportes](docs/assets/workflow-demo.gif)

La animación resume el recorrido operación → cuotas/pagos → cobranza → reportes. Se genera de forma reproducible desde las capturas ficticias con `scripts/build_demo_gif.py`.

| Historial del cliente | Reportes operativos |
|---|---|
| ![Ficha de cliente ficticio](docs/assets/customer-detail-demo.png) | ![Reportes con datos ficticios](docs/assets/reports-demo.png) |

### Ventas y préstamos en un mismo flujo

![Formulario demo para registrar un préstamo](docs/assets/loan-form-demo.png)

El préstamo se modela como una operación financiera y no como un producto ficticio. Así, los rankings de productos siguen siendo consistentes y los saldos reutilizan el mismo motor de cuotas, pagos y recargos.

## 🧱 Arquitectura

```mermaid
flowchart LR
  A[Interfaz Django] --> B[Servicios de dominio]
  B --> C[Modelos y reglas financieras]
  C --> D[(SQLite local)]
  B --> E[PDF y CSV]
  D --> F[Backups y restauración]
  G[Lanzador Windows] --> A
  G --> H[Acceso móvil temporal]
```

| Capa | Responsabilidad |
|---|---|
| `app/modules/core/models.py` | Integridad de clientes, operaciones, cuotas, pagos y visitas. |
| `app/modules/core/services/` | Saldos, recargos, pagos, reportes, exportaciones y PDF. |
| `app/templates/` + `app/static/` | Interfaz responsive y vistas imprimibles. |
| `launcher/` | Inicio local, backups, restauración y acceso móvil temporal. |
| `scripts/` | Instalación, pruebas y construcción del portable. |

## 🧰 Stack

- Python 3.12
- Django 5.2
- SQLite
- Pytest + Coverage
- Ruff
- PyInstaller para la distribución portable
- HTML, CSS y JavaScript sin framework de frontend

## ▶️ Inicio rápido para desarrollo

En Windows, desde la raíz del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\InstalarDesarrollo.ps1
```

Después se puede iniciar con:

```text
scripts\Iniciar.bat
```

O ejecutar el servidor con consola:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Desarrollo.ps1
```

## 🧪 Demo reproducible y segura

La demo debe ejecutarse contra una carpeta separada para no tocar una base real:

```powershell
$env:GESTION_DATA_DIR="$PWD\tmp\demo\data"
$env:GESTION_BACKUP_DIR="$PWD\tmp\demo\backups"
$env:GESTION_EXPORT_DIR="$PWD\tmp\demo\exports"
$env:GESTION_MEDIA_DIR="$PWD\tmp\demo\media"

.\.venv\Scripts\python.exe app\manage.py migrate --noinput
.\.venv\Scripts\python.exe app\manage.py seed_demo_data --confirm-reset
.\.venv\Scripts\python.exe app\manage.py runserver
```

> ⚠️ `seed_demo_data --confirm-reset` elimina los datos comerciales de la base seleccionada. Por eso el ejemplo dirige todas las carpetas a `tmp/demo/`.

## ✅ Calidad verificada

Validación local del 13/08/2026:

- **212 pruebas aprobadas**;
- **88% de cobertura** de líneas y ramas combinadas;
- análisis de Ruff sin observaciones;
- `manage.py check` sin errores;
- ninguna migración pendiente.

Para repetir los controles:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Probar.ps1
```

El workflow de CI ejecuta análisis estático, chequeos de Django, control de migraciones, pruebas y cobertura mínima del 85% en cada push y pull request.

## 📦 Entrega portable

La aplicación puede construirse como carpeta y ZIP portable versionado:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ConstruirPortable.ps1
```

El proceso ejecuta pruebas, genera los ejecutables, valida una copia aislada y crea un manifiesto de integridad. Para `v1.0.0`, los resultados locales son `portable/GestionFinanciera-v1.0.0-windows-x64.zip` y `portable/SHA256SUMS.txt`.

Antes de publicar, el gate de seguridad vuelve a extraer el ZIP, rechaza datos o secretos, repite el smoke test y ejecuta Microsoft Defender:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\AuditarPaqueteRelease.ps1 `
  -ArchivoZip .\portable\GestionFinanciera-v1.0.0-windows-x64.zip `
  -ReportPath .\portable\release-audit.json
```

Los binarios, ZIP y carpetas generadas **no se versionan en Git**: se adjuntan a [GitHub Releases](https://github.com/HeKoXCode/gestion-financiera-local/releases) junto con `SHA256SUMS.txt`, el reporte de auditoría y las notas del [changelog](CHANGELOG.md). La versión `v1.0.0` no tiene firma Authenticode; la decisión, el posible aviso de SmartScreen y la evidencia completa están documentados en [GF-I1 a GF-I4](docs/I1_I4_RELEASE.md).

## 💾 Datos, respaldo y recuperación

```text
data/       Base SQLite y clave local
backups/    Copias de seguridad
exports/    Exportaciones CSV
storage/    Bases archivadas
media/      Logo y archivos cargados
```

Estas carpetas conservan únicamente sus `.gitignore`; su contenido no entra al repositorio. El restaurador valida el ZIP y crea una copia preventiva antes de reemplazar la base activa.

Para archivar una base completa y comenzar otra:

```text
scripts\ArchivarYReiniciar.bat
```

## 📱 Acceso desde celular

El modo móvil está desactivado al iniciar. Cuando el usuario lo habilita:

1. el servidor escucha temporalmente en la red local;
2. se genera una clave aleatoria para esa ejecución;
3. el QR contiene la dirección y la clave temporal;
4. el acceso se invalida al desactivarlo o cerrar la aplicación.

No se abre ningún puerto del router ni se habilita acceso desde Internet. La configuración detallada está en [ACCESO_DESDE_CELULAR.md](docs/ACCESO_DESDE_CELULAR.md).

## ⚠️ Alcance y limitaciones

- Diseñada para una sola persona y una instalación local.
- No incluye cuentas multiusuario, sincronización cloud ni acceso público por Internet.
- SQLite es adecuado para este alcance local; no se presenta como arquitectura empresarial distribuida.
- No reemplaza un sistema contable, fiscal, bancario ni asesoramiento profesional.
- Los cálculos dependen de las reglas configuradas y deben verificarse antes de utilizarlos para decisiones reales.
- El usuario es responsable de conservar respaldos externos y proteger el equipo.

## 📚 Documentación

El [índice de documentación](docs/INDEX.md) separa el plan vigente, las guías operativas, la evidencia de calidad y los documentos históricos.

Documentos principales:

- [Plan vigente del MVP local](docs/PLAN_MVP_LOCAL.md)
- [Reglas financieras](docs/FASE_0_REGLAS_FINANCIERAS.md)
- [Acceso desde celular](docs/ACCESO_DESDE_CELULAR.md)
- [Manual de uso portable](docs/MANUAL_USO_PORTABLE.txt)
- [Guía de entrega](docs/GUIA_DE_ENTREGA_AL_CLIENTE.md)
- [Préstamos integrados](docs/PRESTAMOS_2026-08-06.md)
- [Release portable y evidencia GF-I1 a GF-I4](docs/I1_I4_RELEASE.md)
- [Política de seguridad](SECURITY.md)

## ⚖️ Licencia

El código y la documentación original se distribuyen bajo la [licencia MIT](LICENSE). Los nombres y marcas de terceros pertenecen a sus respectivos titulares.

---

**Percy Ignacio Marzoratti Hill**<br>
*Aplicación gratuita de gestión financiera local · Product Engineering*
