# Fase 4: cobranza y pagos

Versión: 1.0  
Estado: terminada  
Fecha: 24/07/2026

## Objetivo

Completar el circuito financiero diario:

```text
cuotas vencidas → recargo diario único → cobranza → pago → aplicación → saldo
```

El circuito funciona localmente, con importes decimales exactos y sin depender
de Internet.

## Actualización automática del recargo diario

Al abrir el sistema, el lanzador:

1. aplica migraciones;
2. aplica, si corresponde, un recargo por día para cada venta atrasada;
3. crea el backup de inicio;
4. abre el panel local; el navegador se inicia únicamente al presionar
   “Abrir sistema”.

La portada y la pantalla de cobranza también actualizan el recargo diario.
Esto cubre el caso en que el sistema permanece abierto durante la noche.

El proceso es idempotente: abrir o actualizar varias veces no duplica cargos.

## Pantalla de cobranza

La cobranza agrupa las cuotas por venta para evitar filas repetidas. Cada ficha
muestra:

- cliente;
- dirección, barrio y referencia;
- producto;
- primera cuota pendiente;
- cantidad de cuotas vencidas;
- días de atraso desde la más antigua;
- capital vencido acumulado;
- recargos pendientes;
- total a cobrar;
- registrar pago;
- “No pagó”;
- otra visita;
- WhatsApp;
- acceso al detalle.

También resume:

- clientes a cobrar;
- total esperado;
- clientes atrasados;
- deuda atrasada;
- total cobrado en la fecha.

Es posible consultar días anteriores o futuros. Los pagos solo aceptan fechas
de hoy o anteriores. Una venta finalizada desaparece de la cobranza actual,
pero puede reconstruirse en fechas anteriores al pago.

## Registro de pagos

El formulario muestra:

- deuda exigible;
- capital;
- recargos;
- monto abonado;
- fecha;
- método;
- observaciones.

Se admiten pagos completos y parciales. No se permite:

- importe cero o negativo;
- pago futuro;
- pago anterior a la entrega;
- método no configurado;
- pago superior a la deuda exigible;
- intento de adelanto desde el pago normal o mientras la opción permanezca desactivada;
- pago sobre una venta cancelada o finalizada.

## Distribución automática

El pago se aplica en este orden:

1. recargo diario acumulado de la venta;
2. capital pendiente de las cuotas vencidas, desde la más antigua.

El pago normal suma todas las cuotas que ya vencieron, pero nunca invade cuotas
futuras. El flujo separado de adelanto sólo está disponible cuando la venta está
al día y aplica el dinero desde la próxima cuota futura pendiente.

El adelanto puede cubrir una parte, una cuota completa o varias cuotas futuras.
Las fechas semanales, quincenales o mensuales no se recalculan y no se agregan
días de gracia. Si queda un saldo parcial, vence en su día original.

Todas las aplicaciones se crean en la misma transacción que el pago. Si una
validación falla, no queda un pago incompleto.

## Prevención de duplicados

Cada formulario recibe una clave de operación única. Si el navegador reenvía
la misma solicitud, el servicio devuelve el pago existente y no crea otro.
Además, el botón se desactiva visualmente durante el guardado.

## Estado de venta

Después de un pago:

- si queda cualquier capital o recargo, la venta continúa activa;
- si todas las cuotas quedan en cero, pasa automáticamente a finalizada.

Las cuotas futuras mantienen la venta activa aunque toda la deuda del día haya
sido cancelada.

## Anulación

Un pago se anula indicando un motivo:

- no se elimina;
- conserva importe, fecha, método y aplicaciones;
- deja de descontarse del saldo;
- una venta finalizada vuelve a activa si reaparece deuda;
- se reconstruye la única cadena diaria de la venta.

## Intentos de cobranza

La acción rápida “No pagó” registra el resultado sin alterar el saldo. También
puede guardarse:

- ausente;
- prometió pagar;
- otro;
- observaciones.

Una restricción impide duplicar el mismo resultado para la misma venta y fecha.

## WhatsApp manual

Cuando el cliente tiene teléfono, se genera un enlace `wa.me` con:

- nombre;
- importe;
- vencimiento;
- mensaje de Configuración.

El sistema abre WhatsApp y la persona revisa y envía el mensaje manualmente.
No utiliza API, automatización, cuentas de Meta ni costos por mensaje.

## Migración

```text
core.0003_collectionattempt_attempt_unique_sale_date_result
```

Antes de aplicarla se creó un backup. La comprobación posterior de SQLite
respondió `ok`.

## Verificación

Se probaron:

- recargo diario al abrir;
- varias cuotas vencidas sin duplicar un mismo día;
- recargo antes que capital;
- rechazo de un pago que intentaría invadir la cuota siguiente;
- pago parcial;
- saldo restante;
- rechazo de sobrepago;
- rechazo de un adelanto desde el pago común;
- adelanto parcial y completo sin desplazar el cronograma;
- adelanto de varias cuotas futuras en orden;
- métodos inválidos;
- prevención de duplicados;
- finalización automática;
- anulación y reactivación;
- reconstrucción del recargo diario único;
- agrupación de cobranza;
- historial por fecha;
- “No pagó” sin modificar saldo;
- visitas detalladas;
- normalización de teléfono argentino;
- mensaje de WhatsApp.

Resultado:

```text
73 pruebas aprobadas
Cobertura: 91 %
Django check: sin errores
Ruff: sin errores
Migraciones pendientes: ninguna
Integridad SQLite: ok
```

## Estado de portabilidad

Actualmente el sistema ya se abre con `scripts\Iniciar.bat` en esta PC y
funciona sin Internet. Esta modalidad utiliza el Python instalado dentro del
entorno de desarrollo.

La carpeta verdaderamente portable, con `GestionFinanciera.exe` y sin requerir
Python instalado, se construirá en la Fase 8 mediante PyInstaller.

## Próximo paso

Fase 5: completar dashboard, agenda e historial consolidado del cliente.
