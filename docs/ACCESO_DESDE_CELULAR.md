# Acceso portable desde celular

## Objetivo

Permitir que una sola persona utilice Gestión Financiera desde un celular
conectado a la misma red local que la computadora, sin crear usuarios, depender
de Internet ni dejar una dirección fija ligada a una PC.

## Funcionamiento

El modo celular comienza siempre desactivado. Al presionar `Usar desde celular`,
el lanzador:

1. detecta la dirección IPv4 privada elegida por Windows;
2. genera una clave aleatoria de 256 bits;
3. reinicia únicamente el servidor interno para escuchar en la red;
4. incorpora la IP detectada a los dominios admitidos por Django;
5. muestra un QR con la dirección y la clave temporal.

La computadora continúa entrando mediante `127.0.0.1`. El celular utiliza una
dirección del tipo:

```text
http://192.168.1.20:8765/acceso-celular/?clave=CLAVE_TEMPORAL
```

La IP se vuelve a detectar en cada computadora y puede cambiar sin modificar el
código.

## Protección

- Una solicitud proveniente de la propia PC se admite normalmente.
- Una solicitud proveniente de otro equipo necesita una sesión emparejada.
- El emparejamiento solo se obtiene con la clave completa incluida en el QR.
- En la sesión se guarda un resumen criptográfico, no la clave original.
- Al reiniciar el sistema se genera otra clave y las sesiones anteriores dejan
  de ser válidas.
- Una dirección de retorno manipulada no puede sacar al navegador del sistema.
- Al cerrar Gestión Financiera desaparece el servidor y, por lo tanto, el
  acceso.

El modo protege contra el acceso casual de otro equipo conectado a la red. Como
se utiliza HTTP local, no está pensado para redes públicas, Wi-Fi compartido ni
acceso directo desde Internet.

## Firewall de Windows

La entrega incluye:

```text
HABILITAR_ACCESO_CELULAR.bat
DESHABILITAR_ACCESO_CELULAR.bat
```

El habilitador solicita elevación de Windows y crea una regla por puerto, no por
ruta de archivo. Por eso la carpeta puede moverse sin invalidarla. La regla:

- admite TCP en el puerto 8765;
- limita el origen a `LocalSubnet`;
- no abre ni modifica el router;
- permanece inofensiva cuando el sistema está cerrado, porque no hay ningún
  servidor escuchando.

El deshabilitador elimina la regla y es seguro ejecutarlo aunque ya no exista.

## Portabilidad

Los scripts se copian automáticamente al paquete portable. No guardan la IP, la
clave, el nombre de la red ni la ubicación del ejecutable. En una PC nueva:

1. se conserva la carpeta completa;
2. se ejecuta el habilitador una sola vez si Windows bloquea el QR;
3. se abre el sistema y se genera un QR nuevo.

## Límites intencionales

- Solo IPv4 privada.
- Solo red local.
- Puerto fijo 8765 en la entrega para que la regla sea previsible.
- No se activa automáticamente al iniciar.
- No reemplaza las copias de seguridad ni habilita acceso remoto por Internet.
