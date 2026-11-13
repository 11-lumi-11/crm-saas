# Colección de flujos principales

Importa `CRM-SaaS-flujos-principales.postman_collection.json` en Postman. Es una colección adicional; no modifica ni reemplaza `CRM-SaaS.postman_collection.json`. Las URL iniciales corresponden al despliegue `dev` del 12-nov-2026 en `us-east-1`.

## Antes de empezar

- La colección **crea datos reales de prueba en AWS**: empresa, administrador, gerente, cliente, producto, oportunidades, cotizaciones y una actividad. No los elimina al terminar.
- Revisa las URL en las variables de la colección si el equipo vuelve a desplegar las API. `contrasena_demo` contiene una contraseña de ejemplo y se puede cambiar antes de registrar la empresa.
- Selecciona **No environment** en Postman o asegúrate de que el entorno seleccionado no sobrescriba las variables de esta colección, especialmente las URL y los tokens.
- Ejecuta las peticiones **manualmente y en orden**. La primera genera nombres y correos únicos y limpia los identificadores de la ejecución anterior. No la repitas a mitad del recorrido, porque se perderán las referencias anteriores en la colección.
- El login guarda los tokens y las creaciones guardan los identificadores automáticamente en las variables de colección. Si un paso falla, revísalo y resuélvelo antes de continuar. Tras crear un usuario, si el login devuelve 401, espera unos segundos y vuelve a intentarlo: el índice de correo puede tardar en actualizarse.

## Flujos incluidos

1. **Preparación:** registrar empresa y administrador, crear e iniciar sesión como gerente, crear cliente y comprobar el aviso generado por `cliente.creado`.
2. **Venta exitosa:** crear oportunidad, avanzar de etapa y comprobar el seguimiento automático; crear producto y cotización, enviarla, verificar su seguimiento, solicitar la aceptación y comprobar oportunidad ganada y aviso para el gerente. El aviso se puede marcar como leído.
3. **Venta perdida:** crear otra oportunidad y una actividad, enviar una cotización, marcar la oportunidad como perdida y comprobar que la actividad se cancela. Después se solicita aceptar la cotización y se comprueba que vuelve a `enviada` con el motivo de rechazo y que la oportunidad sigue perdida.

La carpeta 3 necesita el cliente de la carpeta 1 y el producto creado en el paso 2.4.

## Eventos y tiempos de espera

Los publicadores de outbox se ejecutan cada minuto y SNS/SQS procesan los eventos de forma asíncrona. Una consulta puede devolver datos anteriores mientras se propagan. Espera y repite **la petición GET de comprobación** cada 20–30 segundos; la coordinación de aceptación puede tardar varios minutos porque usa publicadores de dos servicios. Si hay un cursor `siguiente` en un listado, revisa también las páginas posteriores antes de concluir que no existe el aviso o la actividad.

Una prueba de Postman marcada como fallida mientras la cotización está `aceptacion_pendiente` o el evento aún no llega indica que la condición esperada todavía no se observa. Repite el GET; si no cambia después de varios minutos, revisa los outboxes, los logs y las DLQ en AWS. Evita repetir los POST y los PUT de aceptación: pueden crear registros duplicados o provocar un conflicto de estado.

La respuesta `202` de aceptación solo confirma que se recibió la solicitud. El resultado real se comprueba en `GET /cotizaciones/{cotizacion_id}`. Las peticiones no fuerzan la publicación de eventos ni envían mensajes directamente a SNS.

El contenido de esta colección se preparó a partir del código y las URL de despliegue. **Su ejecución en AWS y sus resultados no se han acreditado todavía.**
