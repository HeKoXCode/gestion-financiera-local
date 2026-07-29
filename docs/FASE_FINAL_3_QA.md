# FaseFinal3: QA, debugging y pruebas de desarrollo

## Objetivo

Esta fase convierte los riesgos de la auditoría en verificaciones repetibles.
No depende solamente de probar botones a mano.

## Suite automática

La suite contiene 159 pruebas y cubre:

- modelos, restricciones e integridad;
- generación semanal, quincenal y mensual;
- reparto de importes con centavos;
- recargos, domingos y pagos parciales;
- pagos, idempotencia y anulaciones;
- clientes, productos, ventas y cancelaciones;
- Dashboard, Cobranza, Semana, Historial y Reportes;
- impresión A4;
- configuración y mensajes de WhatsApp;
- backup, compresión, retención y restauración;
- exportaciones relacionales CSV;
- migraciones y paquete portable;
- cartera demo integral;
- fechas, importes y configuraciones extremas;
- exactitud de consultas históricas;
- límites de consultas para impedir el regreso del problema N+1.

Cobertura medida: 90 % de líneas y ramas combinadas. El mínimo exigido por el
control final es 85 %.

## Ejecución completa

Desde la carpeta del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\FaseFinal3-QA.ps1
```

El control ejecuta, en orden:

1. análisis estático;
2. validación de Django;
3. detección de migraciones olvidadas;
4. las 159 pruebas;
5. medición de cobertura;
6. copia temporal y aislada del portable;
7. apertura de servidor y rutas;
8. verificación de recursos visuales;
9. creación y validación de backup;
10. prueba del restaurador.

Para depurar solo el código, sin volver a copiar el portable:

```powershell
powershell -ExecutionPolicy Bypass `
    -File .\scripts\FaseFinal3-QA.ps1 `
    -OmitirPortable
```

El resultado válido termina con `FASEFINAL3 APROBADA`. Cualquier comando,
excepción, ruta HTTP o cobertura incorrecta detiene la ejecución.

## Inspección visual manual

Con la copia ficticia se comprueba en navegador:

- menú lateral y encabezado;
- tarjetas y tablas del Dashboard;
- filtros y acciones de Cobranza;
- seis columnas de la vista Semana;
- listados paginados;
- venta activa, finalizada y cancelada;
- historial largo de un cliente;
- reportes con datos y gráficos;
- formulario de configuración;
- vista previa de impresión A4;
- anchos de 1440 px y teléfono.

No se modifican pagos o ventas desde la inspección visual; la escritura se
comprueba en bases temporales mediante tests.

## Criterio de aceptación

La entrega se acepta solamente si:

- todas las pruebas pasan;
- no hay migraciones pendientes;
- cobertura igual o superior al 85 %;
- las rutas principales responden;
- el portable funciona fuera del proyecto;
- el backup abre y pasa integridad SQLite;
- el restaurador identifica la copia;
- la demostración conserva todos sus escenarios;
- no aparecen errores 500 ni desbordes visibles.
