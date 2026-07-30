# Pulido visual final

## Alcance revisado

La auditoría visual cubrió:

- panel de inicio local;
- resumen diario;
- clientes: listado, formulario e historial;
- productos: catálogo y formulario;
- ventas: listado, alta, detalle y cancelación;
- cobranza: agenda del día, pago, visita y anulación;
- semana;
- reportes;
- configuración;
- datos y respaldo;
- adaptación para escritorio y celular;
- planilla A4, que conserva su estilo específico de impresión.

## Jerarquía de botones

| Nivel | Uso | Apariencia |
| --- | --- | --- |
| Primario | avanzar o confirmar la acción principal | degradado verde y sombra definida |
| Secundario | consultar, imprimir, editar o cambiar fecha | superficie clara con borde |
| Advertencia | registrar que una persona no pagó | degradado ámbar suave |
| Peligro | cancelar una venta o anular un pago | rojo, reservado para acciones destructivas |
| Fantasma | volver, limpiar o cancelar un formulario | bajo contraste y sin competir con la acción principal |
| Compacto | acciones auxiliares dentro de tarjetas | misma jerarquía con menor tamaño |

Todos mantienen área táctil, foco de teclado, estado activo, hover y contraste.

## Decisiones estéticas

- Se mantuvo el verde oscuro como identidad principal.
- Los degradados se limitaron a botones principales, superficies destacadas,
  encabezados financieros y navegación; no se aplicaron como decoración
  indiscriminada.
- Las tarjetas recibieron sombras más suaves y una superficie con variación
  mínima para separarlas del fondo sin sobrecargar la pantalla.
- Tablas, buscadores, campos, etiquetas e iconos comparten bordes y radios.
- Los estados activo, atrasado, cancelado y completado conservan colores
  semánticos diferentes.
- En celular se ocultaron barras de desplazamiento horizontales visuales, pero
  la navegación continúa permitiendo desplazamiento táctil.

## Identidad del negocio

El logo configurado se utiliza en:

1. menú lateral de la aplicación;
2. vista previa de configuración;
3. planilla imprimible;
4. panel local que aparece antes de abrir el navegador.

El panel de inicio también utiliza el nombre configurado como título. Los logos
PNG, JPG, JPEG y WEBP se adaptan a un recuadro de 64 × 64 píxeles sin
deformarse. Si el archivo no existe o no puede leerse, se muestra el monograma
`GF`, por lo que un logo defectuoso nunca impide abrir el sistema.

## Criterio responsive

- Desde tablet, el menú lateral se convierte en navegación horizontal.
- La navegación se desplaza con mouse o gesto sin mostrar barras permanentes.
- Tablas comerciales se convierten en fichas con etiquetas en celular.
- Botones críticos ocupan todo el ancho cuando el espacio es reducido.
- Indicadores y tarjetas pasan de varias columnas a una sola sin perder orden.
- Importes grandes usan tipografía adaptable y números tabulares.
