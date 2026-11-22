# Estado del frontend oficial

La navegación precarga las secciones permitidas y conserva sus datos en memoria durante la sesión. Al volver, muestra los datos cargados y los actualiza en segundo plano si tienen al menos un minuto o quedaron invalidados por un cambio relacionado; el botón Actualizar fuerza una consulta y muestra su progreso. Al recargar la página o cerrar sesión se descartan los datos en memoria. La última sección se conserva por pestaña y usuario al recargar. La aceptación pendiente sigue consultándose mientras la aplicación esté abierta. El usuario informó que la navegación local se siente más fluida; la validación de estos cambios desde Amplify sigue pendiente.

Actualizado: 2026-11-22. El código oficial está en `crm-frontend-main` y conserva el diseño aprobado por el grupo. Se ejecuta como aplicación React/Vite en el navegador. El usuario probó desde localhost con el backend AWS `dev` la persistencia de cliente y oportunidad, la llegada de una notificación y el flujo de envío y aceptación de cotización. El detalle está en la [guía de pruebas](../docs/guia_pruebas_frontend_aws.md). Los flujos desde Amplify aún no se han probado.

**Estado:** el frontend se publicó manualmente en Amplify `dev` el 2026-11-22, trabajo 3 `SUCCEED`. El usuario informó que probó login, subida y descarga de documentos desde el frontend publicado. Las conexiones asíncronas y el problema intermitente de autenticación se describen en [integraciones AWS](../docs/integraciones_aws_demo.md).

## Usuarios y autenticación

- El registro de empresa y el inicio de sesión llaman al servicio de Usuarios. Después de registrar una empresa se pide iniciar sesión: el registro no devuelve un token.
- La URL se configura con `VITE_USUARIOS_URL`; por defecto apunta al servicio `dev` desplegado. No colocar `JWT_SECRET` ni credenciales de AWS en variables `VITE_`.
- El token y los datos necesarios para la sesión se guardan en el navegador. La interfaz restaura la sesión al recargar mientras el tiempo indicado por el login no haya vencido, y la elimina al cerrar sesión.
- La pantalla de Usuarios lista y modifica usuarios reales, permite cargar páginas adicionales y ya no ofrece gestión local simulada. La creación se realiza desde Inicio.
- Prueba manual informada por el usuario el 2026-11-12: registro e inicio de sesión reales, sesión conservada al recargar, cierre de sesión y rechazo de empresa duplicada. Quedan por comprobar en AWS la expiración del token, desactivación de usuario, cambio de rol y los distintos permisos.
- La compilación y las pruebas locales de autenticación pasan con respuestas de API simuladas. La seguridad y el aislamiento los exige el Authorizer en AWS; el estado del navegador no concede permisos por sí mismo.

## Clientes y contactos

- Documentos de cliente: subir (hasta 4 MiB), listar y descargar desde la ficha. Backend y frontend se desplegaron en `dev` el 2026-11-22. El usuario informó que la subida y descarga funcionan desde Amplify; falta comprobar el aislamiento entre tenants.

- Los correos del cliente y del contacto principal son opcionales; el formulario indica que deben confirmar su suscripción para recibir avisos de venta. La pantalla usa `VITE_CLIENTES_URL` y el token de la sesión para listar, crear, consultar y editar clientes y para listar y crear contactos. El archivo de clientes se retiró de la interfaz y la API en el código local. La creación de contactos permite elegir el principal y muestra los errores de la API.
- Los listados permiten cargar páginas adicionales; la búsqueda se aplica únicamente a los clientes que ya se cargaron.
- Prueba manual informada por el usuario el 2026-11-12 con rol admin y API real: crear, editar y agregar contacto funcionan; los cambios permanecen al recargar; archivar oculta el cliente de la vista. El usuario también informó que comprobó aislamiento entre empresas; faltan detalles del procedimiento y otras combinaciones de roles.
- Se asume una base vacía para este cambio; no se restauran registros archivados anteriormente.

## Oportunidades y actividades

- La pantalla de Oportunidades consulta datos reales y permite crear una oportunidad para un cliente real, marcarla perdida con motivo y consultar historial. El envío de cotización inicia la negociación y la aceptación confirmada marca la oportunidad ganada. Permite cargar más oportunidades y clientes. El tablero refleja únicamente las páginas cargadas; editar oportunidades desde la interfaz queda pendiente; el archivo de oportunidades se retiró de la API.
- La pantalla de Actividades consulta tareas reales, permite cargar más y completar pendientes. La creación y edición manual desde el frontend quedan pendientes. El vendedor consulta sus propias actividades; gerente y admin consultan las del tenant. La API sigue aplicando los permisos.
- Prueba manual informada por el usuario el 2026-11-12: creó una oportunidad asociada a un cliente activo, la avanzó a calificada, se generó una tarea automática y pudo completarla; los datos permanecieron al recargar. La actividad puede tardar unos minutos por el outbox y SNS/SQS. Quedan por probar otros roles, tenants y transiciones.
- La información general de Inicio consulta las API reales de clientes, oportunidades y actividades. Los indicadores representan únicamente la primera página y lo indican en la interfaz; la tarea de entrega y las cancelaciones pueden tardar. El acceso inferior dirige a actividades reales.

## Notificaciones

- La pantalla consulta avisos reales dirigidos al usuario o a su rol, permite marcarlos como leídos individualmente, filtrar no leídos y cargar páginas adicionales. Una página filtrada puede estar vacía y aun así ofrecer más resultados.
- La campana consulta periódicamente la primera página y muestra un indicador si allí hay avisos sin leer; no representa un conteo global y no garantiza que no haya avisos pendientes en otras páginas. Los eventos pueden tardar unos minutos en aparecer.
- En la revisión del 2026-11-22 los eventos recientes de envío y aceptación de cotizaciones generaron avisos en AWS para sus destinatarios: creador de la cotización y rol gerente, respectivamente. El admin no recibe automáticamente esos avisos; las cuentas ficticias admin tienen un aviso histórico de bienvenida. El usuario informó que el flujo ya parecía funcionar. Ver [integraciones AWS](../docs/integraciones_aws_demo.md).
- Prueba manual informada por el usuario el 2026-11-12: aparecen avisos de las actividades y otros eventos; permite marcarlos como leídos y conserva la lectura al recargar. Quedan por verificar roles distintos y más de una página.

## Productos y cotizaciones

- Productos usa la API real para listar, crear, editar, activar y desactivar. Solo gerente y admin ven los controles de gestión; la API verifica los permisos. La lista permite cargar páginas adicionales.
- Registrar un envío actualiza el CRM; la cotización se entrega al cliente por separado. Cotizaciones usa oportunidades y productos reales y permite crear borradores, enviar, solicitar aceptación, rechazar y archivar según los permisos. Los productos seleccionados deben estar activos y tener la misma moneda; el backend calcula el total definitivo.
- Solicitar aceptación muestra `aceptacion_pendiente` y consulta el resultado periódicamente; la interfaz no marca la venta como ganada por recibir HTTP 202. Si el backend rechaza la solicitud, se muestra `resultado_aceptacion`. La confirmación depende de publicadores y colas, por lo que puede tardar varios minutos.
- Prueba manual informada por el usuario el 2026-11-12: creó un producto, creó una cotización asociada a una oportunidad y al producto, la envió y solicitó su aceptación. Tras la confirmación asíncrona, comprobó la cotización `aceptada` y la oportunidad `ganada`. La prueba se hizo desde el frontend local contra el backend AWS `dev`, con rol admin.
- El usuario informó que un vendedor no pudo crear productos. No se ha documentado por separado una petición directa a la API para verificar el código de respuesta.
- Quedan por validar la aceptación cuando la oportunidad está perdida, el rechazo de cotizaciones, la persistencia de estos datos tras recargar, los demás roles y la paginación.

## Pendientes funcionales

- Completar el registro del procedimiento de aislamiento y validar otros permisos; verificar el comportamiento con la base vacía.
- Completar edición de Oportunidades y creación/edición manual de Actividades; validar otros roles, tenants y transiciones en AWS.
- Validar Notificaciones con otros roles, dos usuarios del mismo rol y paginación.
- Evaluar indicadores globales en el backend; Inicio muestra explícitamente un resumen limitado a la primera página real.
- Validar Productos y Cotizaciones con AWS para oportunidades perdidas, rechazo de cotizaciones, persistencia tras recargar, otros roles y páginas adicionales.
- Ampliar las pruebas de eventos, aislamiento y roles con datos reales; los outboxes, SNS y SQS pueden añadir demora.
- Evaluar navegación con URL propias y la configuración de redirección de Amplify; actualmente cambiar de pantalla no cambia la URL.
- Verificar desde la URL de Amplify el login y el flujo comercial que ya pasó desde localhost. El frontend publicado usa por defecto el backend `dev`.
- La aplicación Amplify no está conectada a Git: los cambios requieren una nueva compilación y publicación manual. Ver [README.md](README.md).

## Pruebas pendientes para la próxima sesión

El backend se desplegó en AWS `dev`. Algunas pruebas del flujo comercial se ejecutaron desde localhost; quedan pendientes las siguientes comprobaciones y su evidencia detallada. Para iniciar el frontend desde `crm-frontend-main`, ejecutar `npm run dev -- --host 0.0.0.0` y abrir `http://localhost:5173/`. Comprobar la URL mostrada por Vite si el puerto está ocupado.

1. [ ] **Registro y sesión:** registrar una empresa, iniciar sesión, recargar y cerrar sesión; comprobar correo duplicado y contraseña incorrecta.
2. [ ] **Cliente y contacto:** registrar un cliente con correo y agregar un contacto principal; verificar las solicitudes de suscripción y confirmarlas.
3. [ ] **Inicio de venta:** crear oportunidad y cotización con varios productos; registrar el envío y comprobar que la oportunidad pase a `en_negociacion` y se genere un seguimiento para esa cotización.
4. [ ] **Aceptación:** aceptar la cotización y comprobar confirmación, oportunidad `ganada`, cancelación del seguimiento y creación de la tarea de entrega.
5. [ ] **Correo de venta:** tras confirmar las suscripciones, comprobar que el cliente y su contacto principal reciban el aviso y que no lo reciban destinatarios de otro cliente o tenant. Los filtros SNS pueden tardar hasta 15 minutos en propagarse.
6. [ ] **Rechazo y pérdida:** rechazar una cotización y comprobar que la oportunidad permanezca abierta; marcarla perdida con motivo y comprobar la cancelación de actividades pendientes.
7. [ ] **Permisos y aislamiento:** revisar operaciones con vendedor, gerente y admin y comprobar que dos tenants no vean datos ajenos.
8. [ ] **Errores y CloudWatch:** provocar una petición incorrecta, verificar la respuesta y localizar el registro de la Lambda correspondiente sin datos sensibles.

Los eventos y cambios de etapa son asíncronos y pueden tardar varios minutos. Registrar fecha, entorno, pasos y resultados de cada caso; una pila desplegada o una prueba local no acreditan que el flujo funcione en AWS.
