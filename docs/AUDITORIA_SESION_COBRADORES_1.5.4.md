# Auditoría de sesión — Cobradores 1.5.4

Fecha: 17/09/2026<br>
Proyecto: edición estable 01/08<br>
Versión del código: `1.5.4-edicion01ago`

## Resultado

El bloque actual queda aprobado a nivel de código, interfaz y pruebas. No se
generó un portable 1.5.4 porque se decidió postergar el empaquetado hasta
completar el próximo bloque funcional.

La base habitual del proyecto no se usó para la prueba visual. La validación se
realizó en una carpeta aislada con 50 clientes, 70 ventas y 5 cobradores; desde
la interfaz se creó además un sexto cobrador.

## Qué quedó implementado

- Crear un cobrador desde `Preparar planillas` lo muestra inmediatamente como
  tarjeta, lo deja seleccionado y lleva al sector de elección de clientes.
- Crear un cobrador no genera una planilla vacía. El recorrido se crea al
  guardar al menos un cliente.
- Las tarjetas distinguen claramente entre:
  - cobrador sin planilla para la fecha;
  - cobrador con planilla ya preparada;
  - tarjeta seleccionada para trabajar.
- Un cliente aparece una sola vez aunque tenga varias ventas pendientes. Las
  ventas se muestran agrupadas dentro de la misma visita.
- La búsqueda filtra por cliente y por producto/venta.
- Los nombres extensos de productos y ventas ahora se ajustan en varias líneas
  y no quedan ocultos por puntos suspensivos.
- Se conserva el botón de archivo seguro con dos confirmaciones.
- Un parámetro de cobrador inválido o archivado no rompe la pantalla ni queda
  seleccionado.

## Problema real encontrado y corregido

La búsqueda marcaba las filas no coincidentes con el atributo HTML `hidden`,
pero una regla CSS con `display: grid` tenía prioridad visual y las mantenía en
pantalla. Se agregó una regla explícita para que una fila oculta no se renderice.

Este defecto fue detectado al probar la interfaz real con datos ficticios, no
solamente mediante pruebas unitarias.

## Archivos principales revisados

- `app/modules/core/views.py`: alta rápida, selección segura y separación entre
  cobradores con y sin planilla.
- `app/templates/core/collection/routes.html`: tarjetas, agrupación de ventas,
  mensajes y flujo de selección.
- `app/static/css/app.css`: estados visuales, ajuste de textos, comportamiento
  de filas ocultas y diseño responsive.
- `app/modules/core/tests/test_collectors_v15.py`: comportamiento del servidor y
  agrupación por cliente.
- `tests/test_ux_consistency.py`: contratos de estructura, texto y CSS.
- `CHANGELOG.md` y `pyproject.toml`: registro y número de versión.

## Evidencia automática

- `ruff`: aprobado.
- `manage.py check`: aprobado, sin observaciones.
- `makemigrations --check --dry-run`: sin migraciones pendientes.
- Suite completa: 291 pruebas aprobadas y 7 omitidas de forma esperada porque
  corresponden al módulo de préstamos, ausente en la edición estable 01/08.
- Cobertura total: 86 %.
- Revalidación específica al cierre: 24 pruebas aprobadas.

## Evidencia visual y funcional

Se comprobó la pantalla con datos reales de prueba en:

- escritorio: 1366 × 768;
- tablet: 768 × 1024;
- celular: 360 × 800.

Controles realizados:

- sin desborde horizontal;
- tarjetas en dos columnas en tablet y una columna en celular;
- controles de archivo con área táctil de 44 × 44 px;
- alta de cobrador y selección inmediata;
- búsqueda por nombre de cliente y por venta;
- cliente con dos ventas mostrado en una única fila;
- guardado de una planilla con un cliente;
- cambio correcto de tarjeta `Sin planilla` a tarjeta preparada con acciones
  `Cambiar clientes` e `Imprimir planilla`.

## Límites de esta auditoría

- La carpeta no es un repositorio Git. Por eso no existe un diff o commit
  verificable contra una revisión anterior; la trazabilidad se apoya en los
  archivos, pruebas, versión y CHANGELOG.
- Los ejecutables anteriores siguen sin firma Authenticode porque no existe un
  certificado de firma. Sus ZIP se verifican mediante SHA-256.
- No se implementaron todavía pausa de recargo, frecuencia diaria, cobrador
  habitual ni eliminación del selector desplegable. Esas tareas están
  especificadas en `README_VERSION_1.6.md`.

## Estado del portable tras detener el empaquetado

El intento de construir 1.5.4 se detuvo por decisión de alcance. El constructor
había quitado la carpeta expandida de salida, por lo que se restauró exactamente
la versión 1.5.3 desde su ZIP completo ya auditado.

- ZIP completo 1.5.3:
  `504B0A321A4BCA5DB2FFFCD290EAE8D9AC6642F6C9B61CDEA3402068092AAA4B`
- ZIP de actualización 1.5.3:
  `AA8CBD0931B5D9D98C4CE70BC6BFAFA222579FE03A015DFD78F230CC796EC0B9`
- Carpeta expandida restaurada: `portable/GestionFinanciera`.
- No existe un ZIP 1.5.4 y no debe entregarse todavía.
- `build/GestionFinanciera` contiene solo archivos temporales incompletos de la
  construcción interrumpida. El constructor los reemplazará automáticamente en
  el próximo empaquetado.

## Próximo bloque

Continuar desde la Fase 1 del README de próxima etapa. Al terminar las seis
fases, repetir QA integral y recién entonces producir:

1. portable completo;
2. paquete de actualización que preserve datos;
3. sumas SHA-256;
4. auditoría de contenido y Microsoft Defender;
5. smoke test aislado.
