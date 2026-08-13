# Guía de entrega al cliente

Esta guía está dirigida a quien entrega e instala Gestión Financiera. La guía
para la persona que usará el sistema está incluida dentro del paquete como
`LEEME_PRIMERO.txt`.

## 1. Qué carpeta entregar

No entregar toda la carpeta de desarrollo. La entrega correcta es:

```text
portable\GestionFinanciera-v1.0.0-windows-x64.zip
```

También puede copiarse directamente esta carpeta, siempre completa:

```text
portable\GestionFinanciera
```

El ZIP es la opción recomendada porque evita que durante el traslado falte un
archivo. La carpeta de desarrollo contiene código, pruebas y herramientas que
el cliente no necesita.

La entrega portable ya incluye Python, Django, SQLite y los recursos visuales.
En la PC del cliente no hay que instalar Python, Docker, PostgreSQL, Node.js ni
una base de datos externa.

## 2. Estado comprobado antes de la entrega

La construcción validada:

- comienza sin clientes, productos, ventas, cuotas ni pagos de prueba;
- no contiene la base utilizada durante el desarrollo;
- incluye el acceso opcional desde celular;
- incluye `GestionFinanciera.exe`, `Restaurador.exe` y
  `ArchivarYReiniciar.exe`;
- fue ejecutada desde una copia temporal sin Python disponible;
- superó el inicio, las pantallas principales, los archivos visuales, la copia
  de cierre y una restauración.

La release `v1.0.0` se publica junto con `SHA256SUMS.txt`. Para obtener el valor comprobado del archivo descargado:

```powershell
Get-FileHash .\GestionFinanciera-v1.0.0-windows-x64.zip -Algorithm SHA256
```

El resultado debe coincidir exactamente con la línea publicada en `SHA256SUMS.txt`. Si el paquete se vuelve a construir, su tamaño y SHA-256 cambiarán y debe publicarse como una nueva release.

## 3. Preparar el medio de entrega

1. Copiar `GestionFinanciera-v1.0.0-windows-x64.zip` a un pendrive o medio confiable.
2. Conservar una copia idéntica como respaldo de la versión entregada.
3. No añadir bases de prueba al ZIP.
4. Analizar el ZIP con Microsoft Defender antes de copiarlo.
5. Si se desea comprobar su integridad, ejecutar:

   ```powershell
   Get-FileHash .\GestionFinanciera-v1.0.0-windows-x64.zip -Algorithm SHA256
   ```

## 4. Instalación en la PC del cliente

1. Copiar el ZIP a la PC nueva.
2. Hacer clic derecho sobre el ZIP y elegir `Extraer todo`.
3. Colocar la carpeta extraída en una ubicación local y permanente, por ejemplo:

   ```text
   C:\Users\NOMBRE\GestionFinanciera
   ```

4. No ejecutar el sistema dentro del ZIP.
5. No instalarlo en `C:\Program Files`, en una carpeta de red ni en una carpeta
   que otra aplicación sincronice mientras el sistema está abierto.
6. Comprobar que dentro de la carpeta estén juntos:

   ```text
   GestionFinanciera.exe
   Restaurador.exe
   ArchivarYReiniciar.exe
   INICIAR.bat
   RESTAURAR_DATOS.bat
   ARCHIVAR_Y_REINICIAR.bat
   LEEME_PRIMERO.txt
   _internal\
   data\
   backups\
   exports\
   media\
   storage\
   ```

7. Hacer doble clic en `INICIAR.bat` o `GestionFinanciera.exe`.
8. Si Windows SmartScreen avisa que el editor es desconocido, comprobar que sea
   el paquete entregado y usar `Más información` > `Ejecutar de todas formas`.
   No desactivar Microsoft Defender.
9. Esperar a que aparezca el panel de Gestión Financiera.
10. Pulsar `Abrir sistema`.

El sistema abrirá el navegador en una dirección local. El panel de inicio debe
permanecer abierto mientras se trabaja.

## 5. Crear un acceso directo sin separar archivos

No mover `GestionFinanciera.exe` al escritorio. Debe permanecer junto a
`_internal`.

Para crear un acceso directo:

1. hacer clic derecho sobre `INICIAR.bat`;
2. elegir `Mostrar más opciones` > `Enviar a` > `Escritorio (crear acceso directo)`;
3. cambiar el nombre del acceso directo a `Gestión Financiera` si se desea.

El acceso directo puede moverse; la carpeta real del sistema no debe
desarmarse.

## 6. Configuración inicial junto al cliente

Abrir `Configuración` y revisar, en este orden:

1. nombre del negocio;
2. logo opcional PNG, JPG o WEBP de hasta 2 MB;
3. recargo diario;
4. días en los que se realizan cobranzas;
5. frecuencias habilitadas: semanal, quincenal y/o mensual;
6. medios de pago, uno por línea;
7. cantidad máxima de cuotas;
8. si los domingos generan recargo;
9. si el recargo continúa después de un pago parcial;
10. si se permiten pagos adelantados;
11. texto que se prepara al abrir WhatsApp.

Explicar que el recargo configurado se copia en cada venta nueva. Cambiarlo más
adelante no altera retroactivamente las condiciones de las ventas anteriores.

El texto `Sincronizado localmente` significa que los cambios ya están guardados
en esta PC. No significa que exista una nube ni que los datos se hayan enviado
a Internet.

## 7. Acceso opcional desde celular

Este paso puede omitirse si el cliente usará únicamente la computadora.

La primera vez en cada PC:

1. ejecutar `HABILITAR_ACCESO_CELULAR.bat`;
2. aceptar el permiso de administrador de Windows;
3. abrir Gestión Financiera;
4. pulsar `Usar desde celular` en el panel;
5. conectar el teléfono a la misma red Wi-Fi que la PC;
6. escanear el QR.

El QR incluye una clave temporal. Conocer solamente la IP no permite entrar.
La clave cambia cuando se vuelve a abrir el sistema. La PC debe permanecer
encendida, el panel debe seguir abierto y ambos dispositivos deben estar en la
misma red local.

La regla de Firewall solo admite la red local en el puerto 8765. No abre el
router y no permite entrar desde Internet. En un Wi-Fi público o compartido no
conviene habilitar este modo.

Para retirar la regla se usa `DESHABILITAR_ACCESO_CELULAR.bat`.

## 8. Demostración recomendada al cliente

La explicación completa puede hacerse en unos 15 minutos:

1. **Panel de inicio:** mostrar `Abrir sistema`, `Usar desde celular` y
   `Cerrar y respaldar`.
2. **Inicio:** explicar `Así viene el día`, el pendiente, los atrasos, el dinero
   recibido, el saldo total y las prioridades.
3. **Clientes:** mostrar cómo se guarda la información y cómo se consulta un
   historial. Explicar que archivar no borra.
4. **Productos:** mostrar que es un catálogo reutilizable y que archivar no
   elimina ventas anteriores.
5. **Ventas:** explicar precio, pago inicial, total en cuotas, frecuencia,
   cantidad y primera fecha. Mostrar la vista previa dinámica antes de guardar.
6. **Cobranza:** mostrar una fecha, el total exigible, `Registrar pago`,
   `No pagó`, `Otro resultado`, WhatsApp y la planilla imprimible.
7. **Semana:** explicar que sirve para comparar la carga de lunes a sábado y
   decidir el recorrido, no para crear cobranzas manualmente.
8. **Historial:** mostrar ventas, cuotas, pagos, anulaciones y visitas de una
   persona.
9. **Reportes:** mostrar lo cobrado, lo pendiente, morosos, clientes al día,
   mayores deudas y productos vendidos.
10. **Datos y respaldo:** explicar la diferencia entre copia restaurable y CSV.
11. **Archivar y reiniciar:** explicar que guarda una etapa completa antes de
    dejar la base vacía y que no se usa como cierre diario.
12. **Cierre:** hacer énfasis en `Cerrar y respaldar`.

## 9. Explicación sencilla de todas las funciones

### Panel de inicio de Windows

- `Abrir sistema`: abre las pantallas de trabajo en el navegador.
- `Usar desde celular`: crea temporalmente un QR para la misma red Wi-Fi.
- `Cerrar y respaldar`: guarda la copia final del día y apaga correctamente el
  servidor local.

Cerrar solo la pestaña del navegador no cierra el sistema.

### Inicio — “Así viene el día”

Resume lo que interesa para trabajar:

- clientes a cobrar;
- dinero pendiente hasta la fecha;
- clientes atrasados y monto vencido;
- dinero recibido;
- saldo total de todas las ventas activas, incluidas cuotas futuras;
- avance de la cobranza;
- orden sugerido de prioridades;
- próximos vencimientos y últimos pagos.

Se puede revisar otro día desde la franja semanal.

### Clientes

Permite:

- crear y editar clientes;
- guardar nombre, apellido, DNI opcional, teléfono, dirección, barrio,
  referencia del domicilio y observaciones;
- buscar por nombre, DNI, teléfono o domicilio;
- consultar el historial individual;
- imprimir o guardar en PDF el resumen completo de cada cliente;
- archivar y reactivar.

Archivar evita usar al cliente en una venta nueva, pero conserva todas sus
ventas, pagos y datos históricos. No hay borrado destructivo desde la pantalla.

### Productos

Es el catálogo de productos que se elige al registrar una venta. Guarda nombre
y descripción. Un producto puede archivarse y reactivarse sin alterar las
ventas ya registradas.

### Ventas

Una venta relaciona un cliente con un producto y genera automáticamente todas
las cuotas.

Campos principales:

- fecha de entrega;
- precio del producto;
- pago inicial aparte, si el cliente entrega una parte en efectivo o por otro medio;
- total en cuotas;
- frecuencia semanal, cada 2 semanas o mensual;
- cantidad de cuotas;
- vencimiento de la cuota 1.

En la misma pantalla hay buscadores para Cliente y Producto. Se puede escribir
parte del nombre, DNI, domicilio o descripción sin recorrer una lista extensa.

Ejemplo:

```text
Precio del producto:  $600.000
Pago inicial aparte:  $200.000
Saldo del producto:   $400.000
Cantidad:             10 cuotas semanales
Cuota:                $40.000
```

El total en cuotas se calcula automáticamente como precio menos pago inicial aparte.
Solo se activa `Modificar el total que se pagará en cuotas` cuando se pacta un
costo de financiación o un descuento diferente.

Ejemplo con financiación:

```text
Precio del producto:                    $600.000
Pago inicial aparte:                    $200.000
Total acordado que se pagará en cuotas: $500.000
Cantidad:                               10 cuotas
Cuota:                                  $50.000
Total final recibido por la venta:      $700.000
```

La vista previa recalcula importes y fechas antes de confirmar. El servidor
vuelve a calcular al guardar para evitar que un valor viejo del navegador se
use por error. La última cuota absorbe diferencias de centavos.

Si el plan comienza en la entrega, se activa `La cuota 1 vence el día de la
entrega`. Luego debe indicarse expresamente si `Pagó la cuota 1 al recibir el
producto` o si `La cuota 1 quedó pendiente`. En el primer caso se registra un
pago real sobre esa cuota; en el segundo aparece en Cobranza y el recargo comienza
al día siguiente si continúa impaga.

El pago inicial aparte se registra por separado. El cliente puede pagar solamente
la cuota 1 o pagar la cuota 1 más un pago inicial aparte en la misma fecha sin
mezclarlos.

Para incorporar una venta iniciada antes de usar el sistema, se cargan sus fechas
y condiciones originales y se completa `Cantidad total de cuotas ya pagadas`. Si se
indican 11 de 12, el sistema registra 11 pagos separados sobre las primeras 11
cuotas. Debajo muestra los números del 1 al 11: solamente se tocan las cuotas que
se pagaron tarde y, para cada una, se indican sus días de atraso. Las no marcadas
se guardan como pagadas en fecha. La cuota restante conserva su deuda y atraso
reales. Nunca permite dar por pagadas cuotas futuras ni crear una fecha de pago
posterior a hoy.

Ejemplo: si ya pagó 10 cuotas y las cuotas 2 y 7 llegaron 3 y 1 días tarde, se
escribe `10`, se tocan `2` y `7` y se ingresan esos días. El historial mostrará
la demora de cada cuota y los pagos incluirán los recargos que correspondían.

Una venta puede cancelarse indicando un motivo. La cancelación la retira de la
cobranza, pero conserva su historial.

### Cobranza

Muestra las cuotas que vencen en la fecha elegida y las anteriores que todavía
siguen impagas. Por cada venta muestra:

- cliente y domicilio;
- producto;
- cuotas pendientes;
- recargos;
- total exigible;
- cantidad de días de atraso.

Acciones:

- `Registrar pago`: admite pagos completos o parciales;
- `No pagó`: registra la visita sin inventar un pago;
- `Otro resultado`: permite anotar, por ejemplo, que no se encontró al cliente
  o que pidió volver otro día;
- `Abrir WhatsApp`: prepara el mensaje configurado; la persona decide si lo
  envía. No se envían mensajes automáticamente;
- `Ver detalle`: abre la venta completa;
- `Imprimir planilla`: prepara una hoja A4 con espacio para firma y notas.

Los pagos se aplican al saldo pendiente y el sistema recuerda lo que queda. Un
pago cargado por error puede anularse indicando el motivo; no desaparece del
historial.

### Semana

Compara de lunes a sábado:

- clientes con vencimiento;
- cantidad de cuotas;
- monto programado;
- arrastre de deudas anteriores;
- clientes atrasados;
- barrios para recorrer;
- día con mayor carga.

No crea una agenda aparte. Su propósito es ayudar a organizar la semana y abrir
directamente la cobranza del día elegido.

### Historial del cliente y detalle de venta

Conservan:

- datos de contacto;
- productos y ventas;
- todas las cuotas y sus estados;
- recargos;
- pagos normales e iniciales;
- pagos anulados y motivos;
- visitas e intentos de cobranza;
- total abonado y saldo pendiente;
- línea de tiempo de actividad.

Desde el historial del cliente hay tres acciones para el estado de cuenta:

- `Compartir por WhatsApp`: prepara el PDF y el mensaje para el teléfono guardado;
- `Guardar resumen PDF`: descarga el archivo en la computadora o el celular;
- `Imprimir resumen`: abre la hoja A4 y muestra el cuadro de impresión.

En celulares compatibles se abre el menú para compartir el PDF y se puede elegir
WhatsApp. En una computadora, el PDF queda en Descargas y se abre el chat del
número guardado; luego se adjunta ese archivo manualmente. WhatsApp no permite que
una página web adjunte un archivo automáticamente a un chat específico.

La versión para entregar conserva el nombre, ventas, cuotas, vencimientos,
recargos, pagos y saldo. No revela DNI, teléfono, domicilio, referencias,
observaciones internas, visitas de cobranza, medios de pago ni motivos internos de
anulación. El historial interno del sistema sí conserva toda esa información para
el dueño.

### Reportes

Permiten revisar una fecha y muestran:

- cobrado hoy, en la semana y en el mes;
- total pendiente y monto vencido;
- clientes morosos ordenados por deuda vencida;
- clientes con mayor deuda total, incluidas cuotas futuras;
- clientes al día;
- productos más vendidos;
- evolución de los últimos siete días.

### Configuración

Permite adaptar el sistema sin tocar código: negocio y logo, reglas de recargo,
días, frecuencias, medios de pago, máximo de cuotas, adelantos y mensaje de
WhatsApp.

### Datos y respaldo

- `Crear copia ZIP` genera una copia completa que sí puede restaurarse.
- `Descargar ZIP con CSV` genera archivos para abrir con Excel y analizar.
- Las copias disponibles pueden descargarse desde la misma pantalla.

Una exportación CSV no reemplaza una copia de seguridad. Los CSV no reconstruyen
automáticamente todas las relaciones internas.

### Archivar una etapa y empezar desde cero

`ARCHIVAR_Y_REINICIAR.bat` se usa cuando el dueño quiere conservar toda la base
actual y comenzar otra vacía, por ejemplo después de mudarse. No es una acción
de uso diario.

La herramienta exige que el sistema esté cerrado, pide un nombre y obliga a
escribir `ARCHIVAR`. Primero crea y valida una copia completa en `storage` y
recién después limpia los datos activos. Ese archivo puede recuperarse más
adelante con `RESTAURAR_DATOS.bat` y `Elegir otra copia`.

## 10. Copias automáticas y conservación

El sistema crea copias:

- al iniciar;
- antes de actualizar su estructura;
- después de operaciones importantes mediante una copia fija de recuperación;
- al cerrar correctamente;
- antes de restaurar otra base.

Las copias de cierre conservan una por fecha durante 90 días. Si se cierra varias
veces el mismo día, se actualiza la copia de esa fecha. Además conviene copiar
periódicamente un `.sqlite3.zip` a un pendrive o disco externo.

## 11. Restaurar datos

1. Cerrar con `Cerrar y respaldar`.
2. Ejecutar `RESTAURAR_DATOS.bat` o `Restaurador.exe`.
3. Revisar la copia preseleccionada.
4. Para usar otra, elegir `Elegir otra copia`.
5. Confirmar la restauración.
6. Esperar a que el sistema vuelva a abrirse.
7. Comprobar clientes, ventas y cobranza.

El restaurador valida el ZIP, crea una copia preventiva de lo actual y solo
después reemplaza la base. No hay que descomprimir el backup a mano.

## 12. Trasladar el sistema a otra PC

Opción más sencilla:

1. cerrar y respaldar;
2. copiar la carpeta `GestionFinanciera` completa;
3. pegarla en la PC nueva;
4. abrir `INICIAR.bat`;
5. volver a habilitar el acceso celular si se utilizará.

También puede usarse un paquete limpio y restaurar el backup más reciente. No
conviene trasladar solamente CSV.

## 13. Actualizar una instalación que ya tiene datos

Usar `GestionFinanciera-actualizacion-AAAA-MM-DD.zip`, no el paquete de instalación
limpia. Antes de comenzar:

1. cerrar con `Cerrar y respaldar`;
2. conservar una copia del backup más reciente fuera de la carpeta del sistema;
3. no borrar ni renombrar la carpeta actual;
4. extraer la carpeta `GestionFinanciera` del ZIP en la ubicación de la carpeta
   existente;
5. elegir combinar carpetas y reemplazar archivos cuando Windows lo pregunte;
6. abrir el sistema y comprobar clientes, ventas y cobranza.

Ese ZIP excluye expresamente `data`, `backups`, `exports`, `media` y `storage`.
Actualiza el programa sin reemplazar la base, el logo ni los respaldos del cliente.
Las mismas indicaciones se incluyen en `LEEME_ACTUALIZACION.txt`.

Para volver a generarlo después de construir un portable:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\CrearPaqueteActualizacion.ps1
```

## 14. Limitaciones que deben explicarse

- Está diseñado para una persona y no tiene usuarios ni contraseñas internas.
- Los datos viven en la carpeta de esa PC; no existe sincronización en la nube.
- El acceso móvil funciona solamente mientras la PC y el sistema están abiertos.
- Está pensado para un equipo a la vez, no para edición simultánea desde varias
  computadoras.
- WhatsApp abre un mensaje preparado, pero no envía recordatorios automáticos.
- No tiene actualizaciones automáticas; una actualización debe prepararse y
  probarse conservando primero las carpetas de datos.

## 15. Lista final antes de retirarse

- [ ] El ZIP se extrajo completamente.
- [ ] El acceso directo abre el panel.
- [ ] El nombre del negocio es correcto.
- [ ] El logo se ve correctamente, si fue configurado.
- [ ] Recargo, días, frecuencias y medios de pago fueron confirmados.
- [ ] El cliente sabe crear cliente, producto y venta.
- [ ] Entendió la diferencia entre precio, pago inicial y total en cuotas.
- [ ] Sabe buscar clientes y productos dentro de Nueva venta.
- [ ] Sabe cargar cuotas anteriores ya pagadas cuando incorpora una venta vieja.
- [ ] Sabe tocar las cuotas anteriores pagadas tarde e indicar sus días de atraso.
- [ ] Sabe distinguir pago inicial, cuota 1 pagada y cuota 1 pendiente.
- [ ] Sabe imprimir el resumen individual de un cliente.
- [ ] Sabe registrar un pago parcial y `No pagó`.
- [ ] Sabe imprimir la planilla.
- [ ] Sabe crear una copia restaurable.
- [ ] Sabe que CSV es para Excel, no para restaurar.
- [ ] Sabe que `ARCHIVAR_Y_REINICIAR.bat` guarda una etapa y deja la base vacía.
- [ ] Sabe cerrar con `Cerrar y respaldar`.
- [ ] Se probó el QR, si lo usará.
- [ ] Se guardó una copia de seguridad fuera de la PC.
- [ ] Recibió una copia de `LEEME_PRIMERO.txt`.
