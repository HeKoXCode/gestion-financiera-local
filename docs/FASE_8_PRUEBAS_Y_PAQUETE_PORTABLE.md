# Fase 8: pruebas finales y paquete portable

Estado: terminada  
Fecha: 24/07/2026

## 1. Resultado

El MVP quedó disponible como una carpeta portable de Windows:

```text
portable\GestionFinanciera\
```

y como archivo para trasladar o entregar:

```text
portable\GestionFinanciera-portable.zip
```

La carpeta contiene:

```text
GestionFinanciera\
|-- GestionFinanciera.exe
|-- Restaurador.exe
|-- INICIAR.bat
|-- RESTAURAR_DATOS.bat
|-- LEEME_PRIMERO.txt
|-- MANIFEST_SHA256.txt
|-- _internal\
|-- data\
|-- backups\
|-- exports\
`-- media\
```

La entrega se construye con PyInstaller 6.21 en modo carpeta. No necesita que
la computadora de destino tenga Python, Django, Docker, PostgreSQL ni Node.js.

## 2. Separación de código y datos

Los ejecutables y sus dependencias están en la raíz y en `_internal`. Los datos
modificables permanecen fuera:

- `data`: base SQLite y clave local;
- `backups`: copias restaurables;
- `exports`: paquetes ZIP/CSV;
- `media`: logo configurado por el usuario.

Esto permite copiar o actualizar la parte ejecutable conservando las carpetas
de datos. El paquete generado comienza vacío intencionalmente: nunca incorpora
automáticamente la base real utilizada durante el desarrollo.

Para trasladar datos existentes:

1. cerrar el programa de origen con “Cerrar y crear respaldo”;
2. copiar un backup `.sqlite3.zip` a `backups` del paquete portable;
3. ejecutar `RESTAURAR_DATOS.bat`;
4. revisar la copia seleccionada automáticamente;
5. confirmar la restauración; el programa volverá a abrirse automáticamente.

## 3. Construcción reproducible

Desde la carpeta del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\ConstruirPortable.ps1
```

El script:

1. ejecuta Ruff y toda la suite;
2. elimina únicamente salidas anteriores de construcción;
3. genera `GestionFinanciera.exe`;
4. genera `Restaurador.exe`;
5. añade lanzadores y manual;
6. crea las carpetas externas de datos;
7. prueba una copia aislada;
8. genera un manifiesto SHA-256 de todos los archivos;
9. comprime el paquete;
10. abre y lee completamente el ZIP para verificar su integridad.

Opciones para desarrollo:

```powershell
scripts\ConstruirPortable.ps1 -OmitirPruebas
scripts\ConstruirPortable.ps1 -OmitirZip
```

La construcción normal no debe omitir pruebas.

## 4. Prueba portable automatizada

`scripts\ProbarPortable.ps1` copia el paquete a una carpeta temporal y:

- retira las rutas de Python del `PATH`;
- configura proxies inválidos para detectar dependencias web accidentales;
- ejecuta el binario sin abrir navegador ni ventanas;
- crea la base desde cero y aplica migraciones;
- comprueba inicio, clientes, cobranza, reportes y datos;
- comprueba el CSS local;
- detiene el servidor;
- comprueba el backup de cierre;
- ejecuta el restaurador empaquetado;
- comprueba el backup preventivo;
- valida externamente la integridad y estructura de la base;
- elimina la copia temporal cuando todo resulta correcto.

El ensayo nunca usa `data`, `backups`, `exports` o `media` del proyecto real.

Los archivos CSS y JavaScript incluyen automáticamente una versión derivada de
su contenido. Al actualizar el programa, el navegador descarga la estética y
los comportamientos nuevos en lugar de reutilizar una copia anterior.

## 5. Casos obligatorios

| N.º | Caso | Cobertura |
| ---: | --- | --- |
| 1 | Cliente con y sin DNI | Modelos y vistas de clientes |
| 2 | Venta semanal | Generación de cuotas |
| 3 | Venta quincenal y mensual | Intervalo de 14 días y calendario mensual |
| 4 | Redondeo de última cuota | Diferencia de centavos |
| 5 | Pago en término | Motor de pagos |
| 6 | Uno, dos y tres días de atraso | Motor de recargos |
| 7 | Pago parcial | Saldos y cobranza |
| 8 | Recargo después del pago parcial | Configuración financiera |
| 9 | Dos cuotas vencidas | Aplicación a deuda más antigua |
| 10 | Dos ventas de un cliente | Historial consolidado |
| 11 | Pago anulado | Reapertura de saldo |
| 12 | “No pagó” | Intentos de cobranza idempotentes |
| 13 | Cambio de recargo para ventas nuevas | Valor congelado por venta |
| 14 | Comparación de lunes a sábado | Vista semanal |
| 15 | Impresión con 18 clientes | Prueba A4 con nombres y domicilios extensos |
| 16 | Exportación CSV | ZIP relacional compatible con Excel |
| 17 | Backup | Copia consistente y rotación |
| 18 | Restauración | Recuperación y copia preventiva |
| 19 | Ejecución sin Internet | Recursos locales y prueba con proxy inválido |
| 20 | Copia portable en otra carpeta | Ejecución aislada sin Python en `PATH` |

También se simuló un fallo durante la generación de cuotas. La transacción
revierte la venta incompleta, evitando que un corte deje registros a medias.

## 6. Resultados de calidad

```text
112 pruebas aprobadas
90 % de cobertura
Ruff sin observaciones
Django check sin observaciones
Sin migraciones pendientes
Base de desarrollo íntegra
Paquete portable aprobado
ZIP íntegro
```

Tamaño de la compilación validada:

```text
Carpeta: aproximadamente 56,2 MB
ZIP: aproximadamente 26,7 MB
```

El tamaño puede variar ligeramente entre construcciones.

## 7. Seguridad práctica de la entrega

Los ejecutables son locales y no están firmados con un certificado comercial.
Windows SmartScreen podría mostrar una advertencia la primera vez. No se debe
desactivar Windows Defender. Antes de aceptar la ejecución:

- comprobar que el ZIP provenga de la entrega correcta;
- conservar el hash SHA-256 comunicado con la entrega;
- analizar el ZIP con Windows Defender;
- mantener juntos el ejecutable y `_internal`.

`MANIFEST_SHA256.txt` permite revisar que los archivos internos no hayan
cambiado. El ZIP completo puede verificarse en PowerShell con:

```powershell
Get-FileHash .\GestionFinanciera-portable.zip -Algorithm SHA256
```

## 8. Definición de terminado

El MVP cumple la definición del plan:

- abre con doble clic;
- funciona localmente y sin servicios de Internet;
- administra el flujo cliente–venta–cuota–pago;
- calcula atraso, recargo y pagos parciales;
- muestra dashboard, cobranza, semana, historial y reportes;
- imprime la planilla A4;
- crea, descarga y rota backups;
- exporta CSV;
- restaura copias;
- funciona desde una carpeta trasladable;
- no necesita Python instalado;
- supera los 20 casos obligatorios.
