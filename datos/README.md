# Datos ficticios y carga masiva con S3

Esta carpeta genera los **30,000 registros por microservicio** (10,000 por tenant) que pide el
enunciado y los carga en DynamoDB mediante **S3 + Lambda**, sin pasar por las APIs.

```
generar_datos.py ──► datos/salida/<servicio>/importaciones/<tabla>/parte_0001.jsonl
                                 │
                 subida a S3 (consola o cargar_datos.py)
                                 ▼
   Bucket del servicio: crm-<servicio>-<stage>-imp-<cuenta>/importaciones/...
                                 │  evento s3:ObjectCreated (solo *.jsonl bajo importaciones/)
                                 ▼
   Lambda importarDatos del servicio ──► DynamoDB del mismo servicio (lotes de 25)
                                 │
                                 └──► reporte en resultados/<tabla>/parte_0001.json + CloudWatch
```

Cada microservicio tiene **su propio bucket y su propio Lambda**, y ese Lambda solo acepta las
tablas de su servicio: se mantiene la regla de que nadie escribe la base de datos de otro.

| Archivo | Para qué |
| --- | --- |
| `generar_datos.py` | Genera los datos coherentes en `datos/salida/` (solo Python estándar, ~5 s) |
| `verificar_datos.py` | Comprueba coherencia y conteos sobre los archivos generados |
| `cargar_datos.py` | Sube los archivos a los 6 buckets y espera los reportes (opcional; necesita `boto3`) |
| `../compartido/capa_comun/python/crm_comun/importacion.py` | Lógica común del Lambda de importación |
| `../servicios/<servicio>/src/ImportarDatos.py` | Handler de cada servicio, con su lista de tablas permitidas |
| `../tests/test_importar_datos.py` | Pruebas con S3 y DynamoDB simulados (moto) |

## Qué datos se generan

| Servicio | Tabla principal (30,000) | Tablas que la acompañan |
| --- | --- | --- |
| Usuarios y Tenants | `t_usuarios`: 1 admin, 50 gerentes y vendedores por tenant | `t_tenants` (3), `t_tenants_locks` (3), `t_correos_locks` (30,000) |
| Clientes | `t_clientes` | `t_contactos` (~40,000; uno principal por cliente en el 90 %) |
| Oportunidades | `t_oportunidades` | `t_historial_etapas` (~59,000, coherente con la etapa) |
| Actividades | `t_actividades` | `t_oportunidades_control_actividades` (barrera de las perdidas) |
| Productos y Cotizaciones | `t_cotizaciones` | `t_productos` (136) |
| Notificaciones | `t_notificaciones` | `t_lecturas_notificaciones` (~14,000) |

Reglas que respeta (las comprueba `verificar_datos.py`): toda referencia apunta a un registro
existente **del mismo tenant**; el historial solo avanza de `nueva` a la etapa actual; la
probabilidad corresponde a la etapa; `motivo_perdida` solo en perdidas; solo hay cotización
`aceptada` en oportunidades `ganada` (y en ese caso el cambio a `ganada` lo hizo `sistema`);
totales = suma de ítems; ninguna actividad pendiente en oportunidades perdidas; los avisos usan
el mismo `notificacion_id` determinista, `destino` y `orden` que el servicio de Notificaciones.

### Cuentas de demo (contraseña de todas: `Demo2026!`)

| Tenant | Admin | Gerente | Vendedor |
| --- | --- | --- | --- |
| `ten_seguros` · Seguros Andinos | `admin@seguros.pe` | `gerente@seguros.pe` | `marta@seguros.pe` |
| `ten_electro` · ElectroHogar | `admin@electro.pe` | `gerente@electro.pe` | `vendedor@electro.pe` |
| `ten_consultora` · SoftNova Consultores | `admin@softnova.pe` | `gerente@softnova.pe` | `vendedor@softnova.pe` |

Son cuentas ficticias de prueba. Todos los usuarios generados comparten contraseña y hash:
PBKDF2 con 600,000 iteraciones tarda ~0.5 s por contraseña, y 30,000 hashes distintos tomarían
horas. Es una simplificación válida solo para datos de prueba.

### Decisiones de diseño

- **JSON Lines en partes de 5,000 registros:** el Lambda lee línea por línea sin cargar todo en
  memoria y cada archivo se procesa en segundos, lejos del límite de 15 minutos de Lambda.
- **Idempotente:** se escribe con `put_item` por clave primaria. Volver a subir un archivo, o un
  reintento automático de S3 (las invocaciones asíncronas se reintentan hasta 2 veces), no duplica.
- **Sin outbox:** la carga no publica eventos. Con datos históricos se habrían emitido cientos de
  miles de eventos a SNS y Notificaciones habría creado avisos duplicados de lo que ya se carga.
- **Determinista:** la misma semilla (`--semilla 2032`) produce exactamente los mismos datos.

---

## Guía paso a paso en AWS (Windows)

> Cada comando indica dónde se ejecuta. **"PowerShell normal"** = abrir PowerShell sin
> "Ejecutar como administrador". Ningún paso de esta guía necesita PowerShell como administrador.

### Paso 0 · Quién hace la carga

Los buckets y Lambdas viven en la cuenta de AWS Academy donde se despliegan los servicios, y cada
cuenta de AWS Academy es personal. Por eso:

- **Para probar:** cada integrante despliega todo en su propia cuenta (pasos 1 a 8).
- **Para la demo:** quien tiene el despliegue oficial hace los pasos 5 a 8 en su cuenta, después de
  integrar esta rama.

### Paso 1 · Instalar lo necesario (una sola vez)

1. **Python 3.10 o superior** (ya instalado). Comprobar en PowerShell normal:
   ```powershell
   python --version
   ```
2. **Node.js LTS**: descargar el instalador de nodejs.org o, en PowerShell normal:
   ```powershell
   winget install OpenJS.NodeJS.LTS
   ```
   Cerrar y volver a abrir PowerShell después de instalar.
3. **Serverless Framework 4** (PowerShell normal):
   ```powershell
   npm install -g serverless
   serverless --version
   ```
4. **Iniciar sesión en Serverless** (PowerShell normal; abre el navegador):
   ```powershell
   serverless login
   ```
   Los `serverless.yml` declaran `org: percycastro`. Pedir a Percy que te invite a esa organización
   desde app.serverless.com (Org → Team). Si no es posible, cambia `org:` por tu propia organización
   **solo en tu copia local** y no subas ese cambio.
5. **boto3** (solo si usarás `cargar_datos.py`; PowerShell normal):
   ```powershell
   python -m pip install boto3
   ```

### Paso 2 · Credenciales de AWS Academy (cada vez que inicies el laboratorio)

1. En AWS Academy: **Start Lab**, esperar el círculo verde y abrir **AWS Details**.
2. En **AWS CLI**, pulsar **Show** y copiar todo el bloque `[default] ...`.
3. Pegarlo en el archivo `C:\Users\<tu_usuario>\.aws\credentials` (crear la carpeta `.aws` si no
   existe). Desde PowerShell normal se abre así:
   ```powershell
   New-Item -ItemType Directory -Force "$env:USERPROFILE\.aws" | Out-Null
   notepad "$env:USERPROFILE\.aws\credentials"
   ```
4. Las credenciales caducan al terminar la sesión del laboratorio (unas 4 horas): si aparece
   `ExpiredToken`, repetir este paso.

### Paso 3 · Obtener el código

PowerShell normal, en la carpeta donde guardas tus proyectos:

```powershell
git clone https://github.com/11-lumi-11/crm-saas.git
cd crm-saas
git checkout datos-ficticios-s3   # rama con estos cambios, cuando esté publicada
```

### Paso 4 · Desplegar (en tu cuenta)

Preparar la capa PyJWT y el secreto del token (PowerShell normal, desde la raíz `crm-saas`):

```powershell
python -m pip install -r compartido/capa_jwt/requirements.txt --target compartido/capa_jwt/python
$env:JWT_SECRET = python -c "import secrets; print(secrets.token_hex(32))"
```

`$env:JWT_SECRET` dura solo mientras esa ventana de PowerShell esté abierta; desplegar todo desde
la misma ventana. Luego, en este orden (PowerShell normal):

```powershell
cd compartido;                        serverless deploy --stage dev; cd ..
cd servicios/usuarios;                serverless deploy --stage dev; cd ../..
cd servicios/clientes;                serverless deploy --stage dev; cd ../..
cd servicios/oportunidades;           serverless deploy --stage dev; cd ../..
cd servicios/actividades;             serverless deploy --stage dev; cd ../..
cd servicios/productos_cotizaciones;  serverless deploy --stage dev; cd ../..
cd servicios/notificaciones;          serverless deploy --stage dev; cd ../..
```

`compartido` va primero porque contiene la capa `crm_comun` con el nuevo `importacion.py`. Si los
servicios ya estaban desplegados, igualmente hay que volver a desplegar `compartido` y luego los 6
servicios, para que tomen la nueva versión de la capa y creen su bucket.

Comprobación: en la consola de **S3** deben aparecer 6 buckets `crm-<servicio>-dev-imp-<cuenta>`,
y en **Lambda**, 6 funciones `crm-<servicio>-dev-importarDatos`.

### Paso 5 · Generar y verificar los datos

PowerShell normal, desde la raíz `crm-saas`:

```powershell
python datos/generar_datos.py
python datos/verificar_datos.py
```

Debe terminar con `RESULTADO: OK`. Los archivos quedan en `datos\salida\` (no se suben a Git).

### Paso 6 · Subir a S3 — opción A: consola web (no requiere instalar nada)

Para cada uno de los 6 servicios:

1. Abrir **S3** → bucket `crm-<servicio>-dev-imp-<cuenta>`.
2. **Upload** → **Add folder** → elegir `datos\salida\<servicio>\importaciones` → **Upload**.
   Es importante elegir la carpeta `importaciones` (no su contenido): así las rutas quedan como
   `importaciones/t_clientes/parte_0001.jsonl`, que es lo que espera el Lambda.
3. Esperar 1 o 2 minutos y abrir la carpeta `resultados/` del mismo bucket: debe haber un `.json`
   por archivo subido, con `"estado": "completado"`.

| Servicio | Carpeta a subir | Bucket |
| --- | --- | --- |
| Usuarios | `datos\salida\usuarios\importaciones` | `crm-usuarios-dev-imp-<cuenta>` |
| Clientes | `datos\salida\clientes\importaciones` | `crm-clientes-dev-imp-<cuenta>` |
| Oportunidades | `datos\salida\oportunidades\importaciones` | `crm-oportunidades-dev-imp-<cuenta>` |
| Actividades | `datos\salida\actividades\importaciones` | `crm-actividades-dev-imp-<cuenta>` |
| Productos y Cotizaciones | `datos\salida\productos_cotizaciones\importaciones` | `crm-productos-cotizaciones-dev-imp-<cuenta>` |
| Notificaciones | `datos\salida\notificaciones\importaciones` | `crm-notificaciones-dev-imp-<cuenta>` |

### Paso 6 · Subir a S3 — opción B: script

PowerShell normal, desde la raíz `crm-saas`:

```powershell
python datos/cargar_datos.py --stage dev
```

Sube los 70 archivos, espera los reportes y muestra una tabla con el estado de cada archivo.
Termina con código 0 si todo quedó `completado`.

### Paso 7 · Verificar en AWS

1. **Reportes:** `resultados/<tabla>/parte_XXXX.json` en cada bucket (`registros_escritos`,
   `estado`, `duracion_segundos`).
2. **CloudWatch Logs:** grupo `/aws/lambda/crm-<servicio>-dev-importarDatos`; cada archivo deja una
   línea JSON con el resumen.
3. **DynamoDB:** Tables → `dev-t_clientes` → pestaña *Overview* → *Item summary* →
   **Get live item count**. Debe dar 30,000 (el conteo automático de la consola tarda horas en
   actualizarse; el botón cuenta en vivo).
4. **Login real con una cuenta demo** (Postman o PowerShell normal; cambiar la URL por la de tu
   API de Usuarios, que muestra `serverless deploy`):
   ```powershell
   $cuerpo = '{"correo":"marta@seguros.pe","contrasena":"Demo2026!"}'
   Invoke-RestMethod -Method Post -Uri "https://<api-usuarios>.execute-api.us-east-1.amazonaws.com/usuarios/login" -ContentType "application/json" -Body $cuerpo
   ```
   Debe responder con `token`. Con ese token, `GET /clientes` del servicio Clientes debe listar
   clientes de `ten_seguros` y nunca de otro tenant.

### Paso 8 · Evidencias para el informe

Capturas sugeridas: los 6 buckets; la configuración del evento (Bucket → *Properties* → *Event
notifications*); un reporte `completado` en `resultados/`; el log en CloudWatch; el *live item
count* de cada tabla principal (6 capturas con ≥ 30,000); el login de la cuenta demo; y un
listado en el frontend con datos de dos tenants distintos.

## Problemas frecuentes

| Síntoma | Causa y solución |
| --- | --- |
| `ExpiredToken` o `InvalidClientTokenId` | Credenciales de AWS Academy vencidas: repetir el paso 2 |
| `Organization not found` / no autorizado al desplegar | No perteneces a la org de Serverless: ver paso 1.4 |
| `No module named 'crm_comun.importacion'` en los logs | Se desplegó un servicio sin redesplegar antes `compartido`: desplegar `compartido` y luego el servicio |
| No aparece nada en `resultados/` | El archivo no quedó bajo `importaciones/<tabla>/` o no termina en `.jsonl`: revisar la ruta en S3 |
| Reporte con `"estado": "rechazado"` | Se subió una tabla al bucket de otro servicio: el reporte indica las tablas permitidas |
| `serverless remove` falla por el bucket | CloudFormation no borra buckets con objetos: vaciar el bucket desde la consola y repetir |
| El conteo de la tabla no llega a 30,000 | Revisar en `resultados/` qué archivo falta o tiene errores y volver a subir solo ese (la carga es idempotente) |

**Antes de cargar en un entorno con datos previos:** los tenants generados se llaman Seguros
Andinos, ElectroHogar y SoftNova Consultores. Si alguien ya registró una empresa con uno de esos
nombres o un usuario con uno de los correos demo desde la API, habrá dos registros con el mismo
nombre o correo. Conviene cargar en un stage limpio o revisar antes.

**Costo aproximado:** unas 330,000 escrituras en DynamoDB bajo demanda y 140 solicitudes a S3;
menos de 1 USD del crédito de AWS Academy.

## Pruebas locales

```powershell
python -m pip install "moto[s3,dynamodb]" boto3 pyyaml
python -m unittest tests.test_importar_datos -v
```

Crean las tablas leyendo los `serverless.yml` reales, importan los datos generados con el handler
de cada servicio y comprueban conteos, consultas por índice, rechazo de tablas ajenas, líneas
inválidas e idempotencia. Con `$env:CARGA_COMPLETA = "1"` cargan los 330,000 registros (~2 min).
No sustituyen el despliegue real: permisos de LabRole y notificaciones de S3 se verifican en AWS.