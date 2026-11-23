# Frontend del CRM

Aplicación web del CRM, desarrollada con React y Vite. Se conecta a los microservicios mediante API Gateway y muestra la información correspondiente a la empresa del usuario autenticado.

La interfaz incluye inicio de sesión, gestión de clientes y contactos, consulta de oportunidades y actividades, catálogo de productos, cotizaciones y notificaciones. También permite subir y descargar documentos asociados a clientes.

## Ejecución local

Desde esta carpeta:

```sh
npm ci
cp .env.example .env
npm run dev
```

Las variables `VITE_*_URL` de `.env` configuran las URL de los servicios. Por defecto se utiliza el entorno `dev`. No incluyas contraseñas ni credenciales en estas variables, ya que son visibles en el navegador.

Para generar la versión de producción:

```sh
npm run build
```

Los archivos generados se encuentran en `dist/`. Para revisar la compilación localmente, ejecuta `npm run preview`.
