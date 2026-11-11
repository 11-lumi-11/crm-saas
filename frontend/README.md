# Frontend · CRM SaaS

SPA de React, TypeScript, Vite y Tailwind preparada para AWS Amplify.

## Ejecutar localmente

```sh
cd frontend
cp .env.example .env
npm install
npm run dev
```

Configura en `.env` las URL de API Gateway sin barra final. Usuarios, Clientes y Oportunidades usan su URL real cuando está definida. Actividades, Productos/Cotizaciones y Notificaciones devuelven datos de demostración aislados mientras sus variables estén vacías.

```env
VITE_USUARIOS_URL=https://tu-api-usuarios.execute-api.us-east-1.amazonaws.com
VITE_CLIENTES_URL=https://tu-api-clientes.execute-api.us-east-1.amazonaws.com
VITE_OPORTUNIDADES_URL=https://tu-api-oportunidades.execute-api.us-east-1.amazonaws.com
```

Para generar la versión de producción:

```sh
npm run build
```

Amplify usa `amplify.yml` y publica la carpeta `dist`.

## Alcance actual

Incluye shell protegido, login y registro, dashboard, listado/detalle/alta/edición/archivo de clientes y alta de contactos. Las rutas de las fases posteriores aparecen en el shell como estados informativos, sin operaciones de negocio.

El contrato actual de Usuarios no expone una ruta para obtener el nombre comercial de un tenant. La interfaz muestra el identificador del tenant hasta que ese contrato exista; el nombre del usuario se resuelve con `GET /usuarios` tras el login.
