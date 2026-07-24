# Auditoría del entorno y estrategia de portabilidad

Fecha de auditoría: 23 de julio de 2026.

> Nota de alcance: después de esta auditoría el proyecto se simplificó a una
> aplicación local monousuario con Django y SQLite. Docker continúa instalado y
> operativo, pero ya no será necesario para el uso diario ni para abrir la
> versión portable. Ver [PLAN_MVP_LOCAL.md](PLAN_MVP_LOCAL.md).

## Resultado

El equipo está aprobado para desarrollar y ejecutar el sistema. Tiene recursos
de sobra para Django, PostgreSQL, generación de PDF, pruebas y contenedores.

La virtualización AMD está habilitada y fue reconocida correctamente por
Windows. WSL 2 y Docker Desktop están instalados y operativos.

## Equipo comprobado

| Elemento | Resultado |
| --- | --- |
| Sistema operativo | Windows 11 Pro de 64 bits, compilación 26200 |
| Procesador | AMD Ryzen 5 3600, 6 núcleos y 12 hilos |
| Memoria | 31,9 GB |
| Disco C | 55,8 GB libres de 930,5 GB |
| SLAT | Disponible |
| Virtualización en firmware | Habilitada y reconocida por Windows |
| Placa madre | Gigabyte B550 AORUS ELITE AX V2 |
| BIOS | F21a, 13/04/2026 |

## Herramientas comprobadas

| Herramienta | Estado |
| --- | --- |
| Git | Instalado, versión 2.54.0; identidad configurada |
| VS Code | Instalado |
| Python 3.12 | Instalado, versión 3.12.10 |
| Python 3.14 | Instalado, versión 3.14.3 |
| pip | Instalado para Python 3.12 |
| WSL | Instalado, versión 2.7.10; backend predeterminado WSL 2 |
| Docker Desktop | Instalado, versión 4.83.0 |
| Docker Engine | Instalado, versión 29.6.2; Linux x86_64 |
| Docker Compose | Instalado, versión 5.3.1 |
| PostgreSQL / psql | No instalados |
| WeasyPrint | No instalado |
| Node.js / npm | No instalados y no son necesarios para el MVP |
| Puertos 5432, 6379, 8000 y 8080 | Libres durante la auditoría |

Para el proyecto se usará Python 3.12. Es compatible con Django 5.2 LTS y
reduce diferencias entre la ejecución nativa y la imagen Docker.

PostgreSQL y WeasyPrint se instalarán dentro de contenedores. De esta forma no
dependen de librerías globales de Windows y el mismo proyecto podrá ejecutarse
en Windows, Linux o un servidor de nube. La imagen `postgres:18.4-bookworm` ya
fue descargada y ejecutada correctamente.

## Preparación pendiente del equipo

1. Completado: habilitar `SVM Mode` en el BIOS/UEFI.
2. Completado: guardar la configuración, reiniciar y verificarla en Windows.
3. Completado: instalar y verificar WSL 2.
4. Completado: instalar Docker Desktop en modalidad de usuario con backend
   WSL 2 y solamente contenedores Linux.
5. Completado: ejecutar `hello-world`.
6. Completado: ejecutar `python:3.12-slim`.
7. Completado: ejecutar `postgres:18.4-bookworm`.

No hay una distribución Ubuntu de uso general instalada. Docker Desktop no la
necesita porque administra su propia distribución WSL; podrá instalarse más
adelante si aparece una necesidad concreta.

No es necesario actualizar el BIOS solamente para habilitar SVM. La versión
instalada ya es reciente; la actualización de firmware es una operación
separada y no forma parte de la preparación del proyecto.

## Política de portabilidad del programa

La portabilidad significará que el código y la configuración podrán trasladarse
a otra computadora o servidor sin depender de rutas, programas o configuraciones
particulares de este equipo.

Se aplicarán estas decisiones:

- Un solo repositorio para la aplicación web, las tareas programadas y el PDF.
- Imagen Linux basada en `python:3.12-slim`.
- `compose.yaml` con aplicación, PostgreSQL y, más adelante, worker.
- Versiones de dependencias fijadas en el archivo de bloqueo.
- Configuración mediante variables de entorno y archivo `.env.example`.
- Ninguna contraseña, token o clave dentro del repositorio.
- Ninguna ruta absoluta de Windows dentro del código.
- Uso de `pathlib` para manipular archivos.
- Volúmenes separados para la base de datos y archivos subidos.
- Scripts equivalentes para PowerShell y Bash.
- PostgreSQL como base obligatoria para integración y producción.
- SQLite permitido solamente para una demostración aislada o pruebas muy
  rápidas, nunca como fuente de datos real.
- WeasyPrint ejecutado dentro del contenedor Linux.
- Migraciones de Django como única forma de cambiar el esquema.
- Backups exportables con `pg_dump` y procedimiento documentado de restauración.
- Pruebas automáticas ejecutables tanto en Windows como en Linux.
- Interfaz web responsive; no dependerá de una aplicación nativa instalada.

## Estructura portable prevista

```text
GestionFinanciera/
├── app/
│   ├── config/
│   ├── modules/
│   ├── templates/
│   └── static/
├── docker/
│   ├── app/
│   └── postgres/
├── scripts/
│   ├── dev.ps1
│   ├── dev.sh
│   ├── backup.ps1
│   ├── backup.sh
│   ├── restore.ps1
│   └── restore.sh
├── tests/
├── docs/
├── media/
├── backups/
├── compose.yaml
├── Dockerfile
├── pyproject.toml
├── .env.example
├── .gitignore
├── .gitattributes
└── README.md
```

`media/`, `backups/`, archivos `.env`, entornos virtuales y volúmenes de base
de datos no se guardarán en Git.

## Modos de ejecución previstos

### Modo recomendado

```powershell
docker compose up --build
```

Este modo levantará aplicación y PostgreSQL con las mismas versiones en todos
los equipos.

### Modo nativo de respaldo

La aplicación Django podrá ejecutarse con Python 3.12 instalado en el equipo y
una URL de conexión a PostgreSQL definida en el entorno. Este modo permitirá
seguir trabajando si Docker Desktop no estuviera disponible, pero no será el
modo principal para pruebas de integración o generación de PDF.

## Criterio de preparación completa

El entorno fue aprobado para comenzar el desarrollo porque pasaron estas
comprobaciones:

```text
[x] virtualización habilitada
[x] WSL 2 operativo
[x] Docker Engine operativo
[x] Docker Compose operativo
[x] contenedor de prueba ejecutado
[x] Python 3.12 ejecutado en contenedor
[x] PostgreSQL 18.4 ejecutado en contenedor
[x] carpeta del proyecto accesible
[x] puertos de desarrollo disponibles
```

## Referencias oficiales

- [Instalación de WSL](https://learn.microsoft.com/es-es/windows/wsl/install)
- [Docker Desktop para Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
- [Soporte de la placa Gigabyte](https://www.gigabyte.com/Motherboard/B550-AORUS-ELITE-AX-V2-rev-11/support)
