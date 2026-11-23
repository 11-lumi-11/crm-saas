# CRM SaaS

CRM multiempresa desarrollado como proyecto final de **CS2032 Cloud Computing (2026-2)**. Permite a varias empresas gestionar sus clientes, contactos, oportunidades de venta, actividades, productos, cotizaciones y notificaciones desde una aplicación web.

Cada empresa es un *tenant*: sus usuarios y datos están aislados de los demás tenants. En este proyecto, **cliente** significa una cuenta que la empresa registra dentro del CRM; no es la empresa que contrata el servicio.

## Qué incluye

- **Frontend:** aplicación React y Vite en [`crm-frontend-main/`](crm-frontend-main/), publicada manualmente en AWS Amplify.
- **Backend:** seis microservicios serverless en AWS Lambda, con API HTTP API Gateway y persistencia en DynamoDB.
- **Eventos:** publicación y procesamiento asíncrono mediante SNS y SQS. Los servicios usan outbox para reintentar la publicación de eventos.
- **Autenticación:** registro de empresas, inicio de sesión con JWT y un Lambda Authorizer que valida el usuario, tenant y rol vigentes. Las contraseñas nuevas se almacenan con PBKDF2-HMAC-SHA256.
- **Datos de demo:** generador, verificador y herramientas de carga para empresas ficticias en [`datos/`](datos/README.md).

### Microservicios

| Servicio | Responsabilidad |
| --- | --- |
| Usuarios y Tenants | Registro de empresas y usuarios, login y administración de usuarios. |
| Clientes | Clientes, contactos y asignación de responsables. |
| Oportunidades | Pipeline comercial, etapas e historial de ventas. |
| Actividades | Tareas de seguimiento y actividades comerciales. |
| Productos y Cotizaciones | Catálogo de productos y ofertas asociadas a oportunidades. |
| Notificaciones | Avisos derivados de eventos y estado de lectura por usuario. |

Los servicios mantienen sus propios datos y se comunican mediante eventos e identificadores, sin leer las tablas de otro servicio. El tenant de cada operación protegida se obtiene de la identidad validada, no de un valor enviado por el cliente.

## Ejecutar el frontend

Requiere Node.js y npm. Desde la raíz del repositorio:

```sh
cd crm-frontend-main
npm ci
```

Crea `crm-frontend-main/.env` a partir de `.env.example` si necesitas configurar las URL de tus APIs. Define `VITE_USUARIOS_URL`, `VITE_CLIENTES_URL`, `VITE_OPORTUNIDADES_URL`, `VITE_ACTIVIDADES_URL`, `VITE_PRODUCTOS_URL` y `VITE_NOTIFICACIONES_URL` con las URL públicas de API Gateway. Si no las defines, la aplicación usa las URL `dev` configuradas en el frontend.

```sh
npm run dev
```

Para generar el sitio estático de producción:

```sh
npm run build
```

El resultado se guarda en `crm-frontend-main/dist/`. Las variables `VITE_` quedan visibles en el navegador: no pongas secretos, contraseñas ni credenciales de AWS en ellas. Consulta [`crm-frontend-main/README.md`](crm-frontend-main/README.md) para detalles del frontend y su publicación en Amplify.

## Despliegue del backend

Cada carpeta de `servicios/` contiene un stack independiente. El stack compartido (`compartido/`) provee la capa común y la infraestructura de identidad. El despliegue requiere Python 3.14, Serverless Framework 4, una cuenta AWS configurada y permisos para los recursos utilizados. Los servicios están configurados para la región `us-east-1` y el rol `LabRole` del entorno del proyecto.

Despliega desde cada carpeta, usando el mismo `stage` en todos los stacks y siguiendo este orden:

1. `compartido`
2. `servicios/usuarios`
3. `servicios/clientes`
4. `servicios/oportunidades`
5. `servicios/actividades`
6. `servicios/productos_cotizaciones`
7. `servicios/notificaciones`

En cada carpeta:

```sh
serverless deploy --stage dev
```

Usuarios y el Authorizer requieren el secreto JWT como parámetro `SecureString` en AWS Systems Manager Parameter Store: `/crm/<stage>/jwt-secret`. Configúralo de forma segura antes del despliegue; nunca guardes el secreto en Git. Para la preparación de dependencias, migraciones y validaciones del entorno, revisa [`docs/validacion_local.md`](docs/validacion_local.md).

## Estado y documentación

El informe y los documentos del repositorio distinguen entre funcionalidad diseñada, implementada y verificada en AWS. El estado de un flujo no debe inferirse solo porque exista código o configuración. Al **22 de noviembre de 2026**, se reportó el despliegue de los stacks de backend y del frontend `dev`, una carga de datos ficticios y pruebas funcionales parciales; la evidencia completa de todos los servicios y escenarios aún está pendiente.

- [Informe y estado del proyecto](informeLatex.txt)
- [Documento base: arquitectura, contratos y evidencia](docs/documento_base.md)
- [Validación local y preparación de despliegue](docs/validacion_local.md)
- [Guía de pruebas del frontend y seguimiento en AWS](docs/guia_pruebas_frontend_aws.md)
- [Colección de solicitudes Postman](docs/postman/CRM-SaaS.postman_collection.json)
- [Generación, validación y carga de datos ficticios](datos/README.md)

La colección de pruebas locales reproducibles disponible en el repositorio puede ejecutarse con:

```sh
python -m unittest discover -s tests -p "test_*.py" -v
```

Estas pruebas usan dobles de AWS y no sustituyen una validación de integración en una cuenta AWS.
