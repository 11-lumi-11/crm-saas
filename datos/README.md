# Datos ficticios para el CRM

El generador produce 10 000 registros por tenant en la tabla principal de cada uno de los seis servicios, más las tablas complementarias. Las tres empresas son ficticias y sus correos usan dominios reservados `.example.test`. Las cuentas generadas comparten una contraseña de demostración indicada por el generador; deben usarse solo en el entorno de prueba. No se generan confirmaciones ni suscripciones de correo.

La generación usa la fecha fija 2026-11-14 y una semilla para los datos comerciales; el hash de contraseña usa una sal aleatoria. Las oportunidades tienen las etapas actuales, cada oportunidad ganada tiene una cotización aceptada y el conjunto incluye las actividades y controles de cierre correspondientes.

```sh
.venv/bin/python datos/generar_datos.py --salida datos/salida
.venv/bin/python datos/verificar_datos.py --salida datos/salida
```

`datos/salida/` está ignorado por Git. El verificador comprueba cantidades, claves, referencias por tenant y reglas comerciales. La carga valida otra vez, comprueba cuenta, esquemas y nombres de tenants, y escribe directamente a DynamoDB en transacciones de hasta 25 elementos; no usa S3, no invoca Lambda y no emite eventos. Usa hasta cuatro tareas locales en paralelo. Las escrituras son condicionales: si una clave ya existe con otros datos, la carga se detiene; si existe con los mismos datos, se puede reanudar. Si la carga falla, puede haber lotes ya escritos: conserva los archivos generados para reanudar con los mismos valores, incluido el hash de contraseñas. No regeneres antes de reanudar.

```sh
# Primero valida y comprueba las tablas sin escribir:
.venv/bin/python datos/cargar_datos.py --cuenta NUMERO_DE_CUENTA --stage dev
# Después de revisar el resultado, ejecuta:
.venv/bin/python datos/cargar_datos.py --cuenta NUMERO_DE_CUENTA --stage dev --ejecutar
# Finalmente cuenta cada tabla principal y tenant:
.venv/bin/python datos/contar_datos.py --cuenta NUMERO_DE_CUENTA --stage dev
```

El script no registra suscripciones SNS de correo ni reconstruye los eventos históricos del outbox. Para la demo de correo usa clientes creados mediante el flujo normal y destinatarios que hayan confirmado la suscripción. El script no modifica ni elimina registros existentes distintos de los generados.

## Evidencia de carga en `dev`

El 2026-11-22 se cargaron 309 634 registros de 14 tablas en la cuenta de laboratorio terminada en `5495`, región `us-east-1`. Una consulta consistente verificó 10 000 registros para cada uno de los tres tenants en cada una de las seis tablas principales. Se probó el login de las cuentas admin de `ten_seguros` y `ten_electro`, sus listados de clientes y oportunidades, y el acceso de ElectroHogar a un cliente de Seguros Andinos Demo devolvió 404. Los datos se cargaron sin invocar Lambdas para la importación.

El nombre `Seguros Andinos` ya correspondía a otra empresa. El tenant ficticio `ten_seguros` se identificó como `Seguros Andinos Demo`, preservando la empresa original. Se completó la carga tras verificar de nuevo los datos y nombres de tenant.
