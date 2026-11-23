# CRM SaaS | NodoCRM

CRM multiempresa desarrollado por el grupo **NodoCRM** como proyecto final de **CS2032 Cloud Computing (2026-2)**. La aplicación permite a varias empresas gestionar clientes, contactos, oportunidades, actividades, productos, cotizaciones y notificaciones.

Cada empresa que usa el CRM es un *tenant*. Sus usuarios y datos quedan aislados de los demás tenants. En este proyecto, un **cliente** es una cuenta que la empresa registra en su CRM; no es la empresa que contrata el servicio.

## Arquitectura

- **Frontend:** aplicación React y Vite en [`crm-frontend-main/`](crm-frontend-main/), compilada como sitio estático y publicada manualmente en AWS Amplify.
- **API:** Amazon API Gateway HTTP API recibe las solicitudes y las deriva a funciones AWS Lambda escritas en Python 3.14.
- **Datos:** cada microservicio mantiene sus tablas en Amazon DynamoDB, incluidos sus registros de negocio y su outbox de eventos.
- **Identidad:** JWT y un Lambda Authorizer compartido. El Authorizer valida el token y comprueba el estado actual del usuario, tenant y rol.
- **Eventos:** Amazon SNS distribuye eventos del negocio a colas Amazon SQS filtradas por tipo. Lambdas consumidoras procesan los mensajes de forma asíncrona.
- **Archivos:** Amazon S3 guarda documentos de clientes en un bucket privado; DynamoDB conserva sus metadatos.
- **Secretos y observabilidad:** AWS Systems Manager Parameter Store conserva la clave JWT como `SecureString`; CloudWatch recibe logs y métricas de las Lambdas.

## Microservicios y funciones Lambda

Las rutas HTTP protegidas usan el Authorizer compartido. Además de las funciones de API, varios servicios tienen Lambdas programadas o disparadas por colas.

| Servicio | Responsabilidades y ejemplos de funciones |
| --- | --- |
| **Compartido** (`compartido/`) | `authorizer` valida firma y expiración del JWT y revisa que el usuario y tenant sigan activos y que el rol coincida con el vigente. También publica la capa común reutilizada por los servicios. |
| **Usuarios y Tenants** (`servicios/usuarios/`) | `crearTenant` registra una empresa y su administrador; `loginUsuario` autentica y genera el JWT; `crearUsuario`, `listarUsuarios` y `actualizarUsuario` administran usuarios. `publicarEventos` despacha eventos pendientes. |
| **Clientes** (`servicios/clientes/`) | `crearCliente`, `listarClientes`, `obtenerCliente` y `actualizarCliente` gestionan clientes; `crearContacto` y `listarContactos` gestionan contactos. `subirDocumento`, `listarDocumentos` y `descargarDocumento` trabajan con documentos en S3. `prepararCorreoVenta` consume mensajes de eventos relacionados con ventas. |
| **Oportunidades** (`servicios/oportunidades/`) | `crearOportunidad`, `listarOportunidades`, `actualizarOportunidad` y `cambiarEtapa` gestionan el pipeline; `listarHistorial` consulta cambios de etapa. `procesarSolicitudAceptacion` y `procesarCotizacionEnviada` procesan mensajes de cotizaciones recibidos por SQS. |
| **Actividades** (`servicios/actividades/`) | `crearActividad`, `listarActividades`, `actualizarActividad` y `completarActividad` gestionan tareas. `procesarEventosActividades` consume eventos comerciales desde SQS. `continuarCancelaciones`, programada cada minuto, retoma la cancelación de seguimientos de oportunidades perdidas. |
| **Productos y Cotizaciones** (`servicios/productos_cotizaciones/`) | `crearProducto`, `listarProductos` y `actualizarProducto` mantienen el catálogo. `crearCotizacion`, `enviarCotizacion`, `aceptarCotizacion` y `rechazarCotizacion` gestionan ofertas. `procesarResultadoAceptacion` consume resultados desde SQS y `recuperarAceptaciones` busca solicitudes pendientes cada cinco minutos. |
| **Notificaciones** (`servicios/notificaciones/`) | `procesarEventos` convierte eventos recibidos por SQS en avisos para usuarios; `listarNotificaciones` y `marcarLeida` exponen su consulta y lectura. `correosVenta` procesa por separado los eventos necesarios para preparar el envío de correos de venta. |

## Flujo de eventos con SNS y SQS

El stack `compartido` crea un topic SNS central para los eventos del CRM. Cuando un servicio realiza un cambio de negocio, guarda el dato y un evento pendiente en la misma transacción DynamoDB (patrón *outbox*). Su Lambda `publicarEventos`, programada cada minuto, publica los eventos pendientes en SNS y marca los enviados; si hay un fallo, los pendientes pueden reintentarse.

Las colas SQS se suscriben al topic SNS con filtros por tipo de evento. Esto permite que cada consumidor reciba solo los mensajes que necesita, sin llamadas directas entre Lambdas de distintos servicios. Por ejemplo, las notificaciones se generan a partir de eventos de negocio; y la aceptación de una cotización se coordina de forma asíncrona entre Productos y Cotizaciones y Oportunidades. Actividades también consume eventos para crear o gestionar seguimientos.

Las colas de procesamiento tienen colas de mensajes fallidos (*dead-letter queues*, DLQ) para mensajes que exceden sus reintentos. Los consumidores reportan fallos por mensaje para permitir reintentos parciales. La entrega puede ser repetida, por lo que los consumidores implementan deduplicación donde corresponde.

## Documentos de clientes en S3

El servicio Clientes crea un bucket S3 privado, cifrado y con bloqueo de acceso público. Para subir un archivo, la función Lambda valida la identidad y pertenencia del cliente al tenant, recibe el contenido por la API y guarda el objeto en S3; almacena sus metadatos en DynamoDB. Para descargarlo, valida que el documento pertenezca al cliente solicitado y devuelve una URL prefirmada de lectura válida por 60 segundos. Los archivos no se guardan en DynamoDB ni son objetos públicos.

## Ejecutar el frontend

Requiere Node.js y npm. Desde la raíz del repositorio:

```sh
cd crm-frontend-main
npm ci
npm run dev
```

El frontend usa las URL `dev` configuradas en el proyecto si no se definen variables locales. Para apuntar a otro entorno, crea `crm-frontend-main/.env` basándote en `.env.example` y configura `VITE_USUARIOS_URL`, `VITE_CLIENTES_URL`, `VITE_OPORTUNIDADES_URL`, `VITE_ACTIVIDADES_URL`, `VITE_PRODUCTOS_URL` y `VITE_NOTIFICACIONES_URL` con las URL de API Gateway correspondientes.

Para compilar el sitio estático:

```sh
npm run build
```

El resultado se genera en `crm-frontend-main/dist/`. Las variables `VITE_` son visibles en el navegador: no deben contener secretos ni credenciales. La guía de [frontend](crm-frontend-main/README.md) describe las funciones implementadas y la publicación manual en Amplify.

## Despliegue del backend

Los stacks se despliegan individualmente con Serverless Framework 4, Python 3.14 y credenciales AWS con permisos sobre los recursos. La configuración actual usa la región `us-east-1` y el rol de laboratorio `LabRole`. Usa el mismo `stage` para todos los stacks y despliega en este orden:

1. `compartido`
2. `servicios/usuarios`
3. `servicios/clientes`
4. `servicios/oportunidades`
5. `servicios/actividades`
6. `servicios/productos_cotizaciones`
7. `servicios/notificaciones`

Desde cada carpeta:

```sh
serverless deploy --stage dev
```

Antes de desplegar Usuarios y el stack compartido, configura `/crm/<stage>/jwt-secret` en AWS Systems Manager Parameter Store como parámetro `SecureString`. Nunca guardes el secreto en Git. Los pasos de dependencias, migración y validación se documentan en [`docs/validacion_local.md`](docs/validacion_local.md).

## Pruebas locales

Las pruebas reproducibles disponibles en el repositorio usan dobles de AWS y se ejecutan desde la raíz:

```sh
python -m unittest discover -s tests -p "test_*.py" -v
```

No reemplazan pruebas de integración en AWS.

## Documentación y estado

El informe distingue entre funcionalidades diseñadas, implementadas y verificadas en AWS; la existencia de código o configuración no implica por sí sola una validación en AWS. Al **22 de noviembre de 2026**, se reportaron despliegues de los stacks `dev`, publicación del frontend y carga de datos ficticios, además de pruebas funcionales parciales. La evidencia completa de todos los servicios y escenarios sigue pendiente.

- [Informe del proyecto](informeLatex.txt)
- [Documento base: arquitectura, contratos y evidencia](docs/documento_base.md)
- [Validación local y preparación del despliegue](docs/validacion_local.md)
- [Pruebas del frontend y seguimiento en AWS](docs/guia_pruebas_frontend_aws.md)
- [Colección Postman](docs/postman/CRM-SaaS.postman_collection.json)
- [Generación, verificación y carga de datos](datos/README.md)
