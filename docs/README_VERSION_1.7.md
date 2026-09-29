# Gestión Financiera v1.7 — Ventas y préstamos

## Objetivo

La versión `1.7.2` integra el módulo de préstamos de dinero sobre la base estable
`1.6.2`. No reemplaza la lógica ya validada de cobranza: un préstamo se comporta
como otra operación financiada y comparte clientes, cuotas, pagos, recargos,
cobradores, respaldos y Archivo seguro.

La integración se realizó en una copia independiente. La carpeta v1.6.2 y la
base del cliente no se modificaron durante el desarrollo ni el QA.

## Cómo se registra un préstamo

1. Abrir `Operaciones` y elegir `Nueva operación`.
2. Seleccionar `Préstamo de dinero`.
3. Elegir el cliente.
4. Indicar cómo se entregó el dinero: efectivo, transferencia, tarjeta u otro.
5. Ingresar el dinero prestado y el interés total acordado.
6. Elegir frecuencia, cantidad de cuotas y vencimiento de la cuota 1.
7. Revisar el total a devolver y el calendario antes de confirmar.

El interés configurado es total y se aplica una sola vez:

```text
capital prestado + interés total = total a devolver
```

Ejemplo: $300.000 con 20% de interés total produce $360.000 a devolver. Si se
acuerdan 12 cuotas, cada una será de $30.000.

También se puede activar `Usar otro total a devolver` cuando las partes acuerdan
un monto final sin expresarlo como porcentaje. El sistema calcula el porcentaje
equivalente para conservar la trazabilidad.

## Reglas conservadas de v1.6.2

- Cuotas diarias, semanales, cada dos semanas o mensuales.
- Pago de la cuota 1 al entregar, cuando corresponda.
- Carga histórica de cuotas ya pagadas y sus atrasos.
- Pagos completos, parciales, retroactivos y adelantados.
- Un único recargo diario por operación, aunque haya varias cuotas vencidas.
- Pausa y reactivación futura del recargo sin borrar deuda anterior.
- Cobrador habitual y recorridos diarios sin duplicados.
- `Guardar e imprimir` guarda primero la selección visible.
- Ediciones protegidas, cancelaciones y registros inalterables en Archivo seguro.
- Backups, exportaciones CSV, PDF y restauración portable.

## Distinción visual

La identidad general usa azul petróleo y cian para que la aplicación se sienta
clara, moderna y coherente. Los préstamos se distinguen con azul índigo y el
símbolo `$`, manteniendo la misma tipografía, espaciado y jerarquía del resto
del sistema. La interfaz cambia solo los campos que realmente corresponden:

- una venta pide producto, precio y pago inicial aparte;
- un préstamo pide medio de entrega, capital e interés total;
- ambas operaciones muestran el total acordado, plan de cuotas y recargo diario.

El distintivo `Préstamo` aparece en Operaciones, Clientes, Cobranza, recorridos,
detalle, PDF, exportaciones y Archivo seguro.

La ventana inicial y el acceso desde celular comparten esta misma identidad:
encabezado azul petróleo, acciones cian, fondos azulados suaves y un QR azul.
Así no existe un salto visual entre abrir el ejecutable y entrar al sistema.

## Cobranza y cobradores

Ventas y préstamos pendientes aparecen juntos en Cobranza. El cobrador ve la
operación, el total exigible, los días de atraso y el estado del recargo diario.

En `Preparar planillas`, cada fila crece según el contenido. Esto evita que se
superpongan nombres, cobrador habitual, asignaciones, varias operaciones o
importes extensos. Los estados siguen siendo fáciles de distinguir:

- verde: incluido en la planilla actual;
- rojo: asignado a otro cobrador para ese día;
- azul suave: cobrador habitual sugerido.

Las tarjetas continúan distribuyéndose en tres columnas de escritorio, dos en
tablet y una en celular.

## Reportes

Reportes incorpora un resumen compacto de préstamos:

- préstamos registrados;
- capital prestado;
- total acordado a devolver;
- saldo pendiente.

Los rankings generales consideran todas las operaciones. `Productos más
vendidos` conserva únicamente ventas de productos, para no mezclar dinero con
unidades físicas.

## Compatibilidad de datos

No se agregó una migración nueva en v1.7: los campos y la migración de préstamos
ya existían en la base estable, pero la función estaba deshabilitada. Por eso la
actualización conserva las bases de v1.6.2 y simplemente habilita la interfaz y
la lógica completa.

El tipo de una operación es inmutable: una venta no puede convertirse en
préstamo durante una edición, ni un préstamo en venta. Sí pueden corregirse los
datos propios del préstamo dentro de las reglas de edición segura.

## QA profesional

La verificación se ejecuta sobre una base ficticia aislada con:

- 50 clientes;
- 70 operaciones;
- 14 préstamos;
- 5 cobradores;
- escenarios de pagos completos, parciales, anulados, atrasos, pausas y
  recorridos.

Controles obligatorios antes del empaquetado:

1. Ruff sin observaciones.
2. `manage.py check` sin errores.
3. `makemigrations --check --dry-run` sin cambios pendientes.
4. Suite completa de Pytest y cobertura mínima del proyecto.
5. Alta de préstamo y cálculo dinámico en navegador.
6. Revisión visual de listados, detalle, cliente, reportes y planillas.
7. Prueba responsive en escritorio, tablet y celular.
8. Consola del navegador sin errores ni advertencias.
9. Smoke test del portable extraído en una carpeta aislada.
10. Auditoría del ZIP para confirmar que no contiene bases, respaldos ni datos
    del usuario.

## Archivos de entrega

La construcción genera:

```text
portable/GestionFinanciera/                         carpeta lista para usar
portable/GestionFinanciera-v1.7.2-windows-x64.zip   instalación completa
portable/GestionFinanciera-actualizacion-1.7.2.zip  actualización sin datos
portable/SHA256SUMS.txt                              integridad de ambos ZIP
portable/release-audit-v1.7.2.json                   auditoría del paquete
portable/release-audit-update-v1.7.2.json            auditoría de la actualización
```

Para actualizar una instalación existente debe usarse el ZIP de actualización.
Las carpetas `data`, `backups`, `exports`, `media` y `storage` del cliente no se
reemplazan.

## Resultado final verificado

- Versión: `1.7.2`.
- Suite automática: `321` pruebas aprobadas.
- Cobertura: `88 %`.
- Ruff, Django check y migraciones pendientes: sin observaciones.
- QA visual: escritorio y celular, sin desbordes ni errores de consola.
- Portable completo: `63.564.479` bytes.
- Actualización sin datos: `63.567.329` bytes.
- Contenido sensible detectado en los ZIP: `0` archivos.
- Smoke test aislado de ambos paquetes: aprobado.
- Microsoft Defender: aprobado, `0` detecciones en ambos paquetes.

SHA-256:

```text
3AE9F410699232AB67F31FFB84971BBC01516DD7977F713C0362DF4195CCC2C0  GestionFinanciera-v1.7.2-windows-x64.zip
94997F4EAFB8D6FA1BD9FD28BF0887756C66304C66374B5200221E0C6259CCEA  GestionFinanciera-actualizacion-1.7.2.zip
```

Los ejecutables no están firmados digitalmente porque no se dispone de un
certificado de firma de código. Su integridad se verifica con los hashes
publicados en `SHA256SUMS.txt`.
