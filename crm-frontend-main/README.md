# Frontend oficial del CRM

Aplicación React y Vite basada en el diseño aprobado por el grupo. Autenticación, Clientes, Notificaciones, Productos y Cotizaciones, y las funciones integradas de Oportunidades y Actividades usan sus servicios. Los indicadores de Inicio utilizan datos simulados que se reinician al recargar.

El avance, las pruebas y los pendientes se registran en [ESTADO_FRONTEND.md](ESTADO_FRONTEND.md).

## Ejecutar localmente

```sh
cd crm-frontend-main
npm ci
cp .env.example .env
npm run dev
```

`VITE_USUARIOS_URL`, `VITE_CLIENTES_URL`, `VITE_OPORTUNIDADES_URL`, `VITE_ACTIVIDADES_URL`, `VITE_PRODUCTOS_URL` y `VITE_NOTIFICACIONES_URL` identifican las URL públicas de API Gateway. Si no están definidas, se usan las URL del entorno `dev` desplegado por el grupo. Para otra cuenta o entorno, configúralas antes de compilar o en la configuración de compilación de Amplify. Las variables `VITE_` son visibles en el navegador: no deben contener `JWT_SECRET`, contraseñas ni credenciales de AWS.

El registro crea la empresa y luego solicita iniciar sesión; no inicia una sesión automáticamente. Una sesión válida se conserva en el navegador hasta que vence el token o se cierra sesión. Clientes permite listar, crear, editar y archivar clientes y gestionar contactos. Oportunidades permite listar, crear y cambiar etapas; Actividades permite listar y completar; Notificaciones permite consultar y marcar avisos como leídos; Productos y Cotizaciones permiten operar con el catálogo y las ofertas reales. El resto de sus operaciones figura como pendiente en el registro de estado. Los indicadores de Inicio siguen siendo una demostración local y no se sincronizan con los servicios.

```sh
npm run build
```

La compilación genera `dist/`, que Amplify sirve como sitio estático. La publicación `dev` del 2026-11-12 está disponible en [https://dev.d38c15mc7g1yzr.amplifyapp.com](https://dev.d38c15mc7g1yzr.amplifyapp.com). La página respondió HTTP 200; las pruebas funcionales desde esa URL siguen pendientes.

## Publicación manual en Amplify

El stack `crm-frontend-hosting-dev` crea la aplicación y rama de Amplify mediante Serverless Framework y CloudFormation. El código se compila localmente y se publica con el script incluido; no hay conexión a Git ni despliegue automático. Con las credenciales AWS configuradas, desde esta carpeta:

```sh
npm ci
npm test
npm run build
serverless deploy --stage dev
../.venv/bin/python scripts/publicar_amplify.py --stage dev
```

El script necesita boto3 y utiliza los outputs del stack para publicar el contenido de `dist/`. No imprime las credenciales ni la URL prefirmada de carga. Las variables `VITE_` se incorporan durante `npm run build`, no después de subir el paquete. Mantener el mismo entorno y revisar que las URL apunten al backend deseado. Para una versión conectada a Git o con despliegue automático se necesita una configuración adicional.
