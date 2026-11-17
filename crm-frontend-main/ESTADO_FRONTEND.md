# Estado del frontend oficial

Actualizado: 2026-11-12. El código oficial está en `crm-frontend-main` y conserva el diseño aprobado por el grupo. Se ejecuta como aplicación React/Vite en el navegador. Amplify informó publicación exitosa en `dev`, `us-east-1`, en [https://dev.d38c15mc7g1yzr.amplifyapp.com](https://dev.d38c15mc7g1yzr.amplifyapp.com); la página raíz respondió HTTP 200. Los flujos desde esa URL aún no se han probado.

**Estado de Git al cierre:** las correcciones de microservicios se subieron a `main` en el commit `f5e40da`. La carpeta `crm-frontend-main/`, incluido este documento y el código desplegado, permanece sin seguimiento en la copia local y no fue incluida en ese commit. Amplify recibió una compilación manual; la publicación no sustituye guardar el código fuente en Git.

## Usuarios y autenticación

- El registro de empresa y el inicio de sesión llaman al servicio de Usuarios. Después de registrar una empresa se pide iniciar sesión: el registro no devuelve un token.
- La URL se configura con `VITE_USUARIOS_URL`; por defecto apunta al servicio `dev` desplegado. No colocar `JWT_SECRET` ni credenciales de AWS en variables `VITE_`.
- El token y los datos necesarios para la sesión se guardan en el navegador. La interfaz restaura la sesión al recargar mientras el tiempo indicado por el login no haya vencido, y la elimina al cerrar sesión.
- La pantalla de Usuarios tiene llamadas reales para crear, listar y modificar usuarios, pero todavía debe revisarse el manejo de paginación y las diferencias entre datos reales y simulados.
- Prueba manual informada por el usuario el 2026-11-12: registro e inicio de sesión reales, sesión conservada al recargar, cierre de sesión y rechazo de empresa duplicada. Quedan por comprobar en AWS la expiración del token, desactivación de usuario, cambio de rol y los distintos permisos.
- La compilación y las pruebas locales de autenticación pasan con respuestas de API simuladas. La seguridad y el aislamiento los exige el Authorizer en AWS; el estado del navegador no concede permisos por sí mismo.

## Clientes y contactos

- La pantalla usa `VITE_CLIENTES_URL` y el token de la sesión para listar, crear, consultar y editar clientes y para listar y crear contactos. El archivo de clientes se retiró de la interfaz y la API en el código local. La creación de contactos permite elegir el principal y muestra los errores de la API.
- Los listados permiten cargar páginas adicionales; la búsqueda se aplica únicamente a los clientes que ya se cargaron.
- Prueba manual informada por el usuario el 2026-11-12 con rol admin y API real: crear, editar y agregar contacto funcionan; los cambios permanecen al recargar; archivar oculta el cliente de la vista. El usuario también informó que comprobó aislamiento entre empresas; faltan detalles del procedimiento y otras combinaciones de roles.
- Se asume una base vacía para este cambio; no se restauran registros archivados anteriormente.

## Oportunidades y actividades

- La pantalla de Oportunidades consulta datos reales y permite crear una oportunidad para un cliente real, marcarla perdida con motivo y consultar historial. El envío de cotización inicia la negociación y la aceptación confirmada marca la oportunidad ganada. Permite cargar más oportunidades y clientes. El tablero refleja únicamente las páginas cargadas; editar oportunidades desde la interfaz queda pendiente; el archivo de oportunidades se retiró de la API.
- La pantalla de Actividades consulta tareas reales, permite cargar más y completar pendientes. La creación y edición manual desde el frontend quedan pendientes. El vendedor consulta sus propias actividades; gerente y admin consultan las del tenant. La API sigue aplicando los permisos.
- Prueba manual informada por el usuario el 2026-11-12: creó una oportunidad asociada a un cliente activo, la avanzó a calificada, se generó una tarea automática y pudo completarla; los datos permanecieron al recargar. La actividad puede tardar unos minutos por el outbox y SNS/SQS. Quedan por probar otros roles, tenants y transiciones.
- Los indicadores de Inicio conservan datos simulados; no deben usarse para dar por validado el flujo real. El acceso inferior a tareas dirige a la pantalla de actividades reales.

## Notificaciones

- La pantalla consulta avisos reales dirigidos al usuario o a su rol, permite marcarlos como leídos individualmente, filtrar no leídos y cargar páginas adicionales. Una página filtrada puede estar vacía y aun así ofrecer más resultados.
- La campana consulta periódicamente la primera página y muestra un indicador si allí hay avisos sin leer; no representa un conteo global y no garantiza que no haya avisos pendientes en otras páginas. Los eventos pueden tardar unos minutos en aparecer.
- Prueba manual informada por el usuario el 2026-11-12: aparecen avisos de las actividades y otros eventos; permite marcarlos como leídos y conserva la lectura al recargar. Quedan por verificar roles distintos y más de una página.

## Productos y cotizaciones

- Productos usa la API real para listar, crear, editar, activar y desactivar. Solo gerente y admin ven los controles de gestión; la API verifica los permisos. La lista permite cargar páginas adicionales.
- Cotizaciones usa oportunidades y productos reales y permite crear borradores, enviar, solicitar aceptación, rechazar y archivar según los permisos. Los productos seleccionados deben estar activos y tener la misma moneda; el backend calcula el total definitivo.
- Solicitar aceptación muestra `aceptacion_pendiente` y consulta el resultado periódicamente; la interfaz no marca la venta como ganada por recibir HTTP 202. Si el backend rechaza la solicitud, se muestra `resultado_aceptacion`. La confirmación depende de publicadores y colas, por lo que puede tardar varios minutos.
- Prueba manual informada por el usuario el 2026-11-12: creó un producto, creó una cotización asociada a una oportunidad y al producto, la envió y solicitó su aceptación. Tras la confirmación asíncrona, comprobó la cotización `aceptada` y la oportunidad `ganada`. La prueba se hizo desde el frontend local contra el backend AWS `dev`, con rol admin.
- El usuario informó que un vendedor no pudo crear productos. No se ha documentado por separado una petición directa a la API para verificar el código de respuesta.
- Quedan por validar la aceptación cuando la oportunidad está perdida, el rechazo de cotizaciones, la persistencia de estos datos tras recargar, los demás roles y la paginación.

## Pendientes funcionales

- Completar el registro del procedimiento de aislamiento y validar otros permisos; verificar el comportamiento con la base vacía.
- Completar edición de Oportunidades y creación/edición manual de Actividades; validar otros roles, tenants y transiciones en AWS.
- Validar Notificaciones con otros roles, dos usuarios del mismo rol y paginación.
- Conectar los indicadores de Inicio a datos reales; actualmente muestran datos simulados.
- Validar Productos y Cotizaciones con AWS para oportunidades perdidas, rechazo de cotizaciones, persistencia tras recargar, otros roles y páginas adicionales.
- Ampliar las pruebas de eventos, aislamiento y roles con datos reales; los outboxes, SNS y SQS pueden añadir demora.
- Evaluar navegación con URL propias y la configuración de redirección de Amplify; actualmente cambiar de pantalla no cambia la URL.
- Verificar desde la URL de Amplify el login y el flujo comercial que ya pasó desde localhost. El frontend publicado usa por defecto el backend `dev`.
- La aplicación Amplify no está conectada a Git: los cambios requieren una nueva compilación y publicación manual. Ver [README.md](README.md).
