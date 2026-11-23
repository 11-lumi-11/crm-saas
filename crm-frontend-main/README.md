# Frontend del CRM

Aplicación web del CRM, desarrollada con React y Vite. Permite gestionar clientes, oportunidades, actividades, productos, cotizaciones y notificaciones.

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

Los archivos generados se encuentran en `dist/`.
