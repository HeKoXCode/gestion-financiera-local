# FaseFinal1: copia integral de demostración

## Resultado

La demostración se genera en una carpeta temporal separada de la instalación real, por ejemplo `tmp/GestionFinanciera_FaseFinal/`.

Esa carpeta es autónoma. Su base de datos, copias, exportaciones y archivos
multimedia no se mezclan con los de `GestionFinanciera`.

## Cartera ficticia

La fecha de referencia es el 29/07/2026. El generador crea:

- 48 clientes ficticios distribuidos desde tres meses antes hasta la fecha;
- clientes activos y archivados;
- datos opcionales vacíos y completos;
- 14 productos, incluido uno archivado;
- ventas semanales, quincenales y mensuales;
- ventas activas, finalizadas y canceladas;
- operaciones sin entrega y con entrega inicial;
- total en cuotas igual, superior e inferior al saldo del producto;
- cuotas futuras, del día, vencidas, pagadas y parcialmente pagadas;
- recargos de distintos importes y ventas sin recargo;
- pagos en efectivo, transferencia, tarjeta y otro;
- pagos iniciales, pagos de cuotas y pagos anulados;
- visitas con todos los resultados disponibles;
- información suficiente para Dashboard, Semana, Cobranza, Historial y Reportes.

Los nombres, DNI, teléfonos, domicilios y observaciones son inventados.

## Aislamiento

El generador elimina los datos comerciales de la base sobre la que se ejecuta.
Por eso requiere escribir expresamente `--confirm-reset`. No se debe ejecutar
contra la carpeta original.

Ejemplo para reconstruir solamente una base de laboratorio:

```powershell
$env:GESTION_DATA_DIR = "C:\ruta\laboratorio\data"
.\.venv\Scripts\python.exe app\manage.py migrate
.\.venv\Scripts\python.exe app\manage.py seed_demo_data `
    --confirm-reset `
    --as-of 2026-07-29
```

La protección y la cobertura del generador se verifican automáticamente en
FaseFinal3.
