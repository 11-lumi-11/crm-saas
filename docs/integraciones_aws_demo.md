# Integraciones del CRM: revisión antes de la demo

Revisión de solo lectura: 2026-11-22, cuenta de laboratorio terminada en `5495`, región `us-east-1`, stage `dev`. Los estados pueden cambiar; volver a consultarlos antes de la presentación. No se activaron integraciones durante esta revisión.

**Actualización posterior del 2026-11-22:** a pedido del usuario se habilitaron directamente las siete conexiones del CRM; todas quedaron en estado `Enabled`. Los mensajes pendientes de Notificaciones y Actividades dejaron de figurar en sus colas; esto por sí solo no acredita el resultado funcional. La revisión de logs recientes no mostró errores en esos dos consumidores. En el consumidor de correos se observó un error `Destinatarios del cliente aún no registrados`; revisar sus reintentos y DLQ si el correo de venta no llega. No se ha identificado la causa de la deshabilitación anterior; comprobar nuevamente el estado antes de la demo.

**Confirmación informada por el usuario:** después de habilitar las conexiones, las notificaciones volvieron a funcionar. Antes de presentar, comprobar los siete disparadores y habilitar únicamente los que estén deshabilitados, teniendo en cuenta los mensajes pendientes.

**Pendiente de autenticación:** el usuario informa que, después de un periodo sin uso, los primeros intentos de login o registro devuelven `Internal Server Error` durante aproximadamente cinco minutos y luego funcionan. La causa no se ha investigado ni confirmado. Para la presentación, probar login y registro con anticipación suficiente y revisar CloudWatch si ocurre; esperar y reintentar no sustituye un diagnóstico.

## Conexiones SQS a Lambda

Estas siete conexiones del CRM aparecieron en estado **Disabled**, todas con `StateTransitionReason: USER_INITIATED`. Ese texto no identifica al actor ni demuestra por sí solo que una persona las haya desactivado. La última modificación registrada estaba entre las 15:28 y las 15:31 (hora de Lima) del 18 de noviembre. La consulta de CloudTrail para `UpdateEventSourceMapping` no devolvió eventos; la causa no está acreditada.

| Función Lambda (prefijo `crm-` y sufijo `dev` según el nombre completo) | Consecuencia si está deshabilitada |
| --- | --- |
| `crm-notificaciones-dev-procesarEventos` | No procesa los eventos para generar avisos en el CRM. |
| `crm-actividades-dev-procesarEventosActividades` | No procesa eventos para crear o cancelar actividades. |
| `crm-oportunidades-dev-procesarCotizacionEnviada` | No procesa el envío de cotización para actualizar la oportunidad. La cola conserva un nombre físico antiguo relacionado con cotización aceptada. |
| `crm-oportunidades-dev-procesarSolicitudAceptacion` | No procesa las solicitudes de aceptación para cerrar oportunidades. |
| `crm-productos-cotizaciones-dev-procesarResultadoAceptacion` | No aplica a la cotización la confirmación o rechazo de la oportunidad. |
| `crm-clientes-dev-prepararCorreoVenta` | No prepara los destinatarios de correos tras una venta. |
| `crm-notificaciones-dev-correosVenta` | No procesa la gestión y envío de correos de venta. |

También había otras dos conexiones deshabilitadas ajenas al CRM; esta guía no pide modificarlas.

El 22 de noviembre las reglas programadas del CRM aparecían habilitadas y las siete suscripciones SQS del topic `dev-eventos-crm-topic` existían. Esto no acredita que los flujos se procesen: las conexiones Lambda anteriores estaban deshabilitadas. La consulta SQS mostró mensajes visibles en Actividades (1), Notificaciones (2), la cola de cotización enviada (1) y la de solicitud de aceptación (1); los contadores son aproximados y cambian. La retención de esas colas era de cuatro días, por lo que un mensaje puede caducar si no se procesa.

## Comprobación y activación antes de presentar

1. En AWS Console, confirma cuenta, región `us-east-1` y entorno `dev`. En **Lambda**, busca cada una de las siete funciones de la tabla.
2. En cada función, abre **Configuration → Triggers** y localiza el disparador SQS. Comprueba su estado. Si está deshabilitado y el equipo decide reanudar el flujo, selecciónalo y usa **Enable**. No modifiques los disparadores de proyectos ajenos.
3. Antes de habilitar, revisa en **SQS** los mensajes visibles y las DLQ correspondientes. Al habilitar un disparador, Lambda puede procesar de inmediato mensajes pendientes, producir cambios en datos y, para los flujos de correo, enviar mensajes a destinatarios suscritos. Los mensajes que ya vencieron no se recuperan automáticamente.
4. Verifica que los disparadores queden en **Enabled**, que el topic SNS conserve sus suscripciones SQS y que las reglas programadas de publicación sigan habilitadas en EventBridge.
5. Con datos de prueba, crea una oportunidad y envía una cotización; comprueba negociación, seguimiento y avisos. Solicita la aceptación y comprueba la cotización aceptada, la oportunidad ganada y las actividades posteriores. Los eventos son asíncronos y pueden demorar varios minutos. Para correo, usa destinatarios de prueba que hayan confirmado su suscripción.
6. Si un flujo no avanza, revisa CloudWatch Logs de la función, el número de mensajes de la cola y su DLQ. Una cola vacía no demuestra por sí sola el procesamiento correcto. Registrar fecha, tenant y resultado, sin contraseñas ni tokens.

Volver a verificar las conexiones justo antes de la presentación: hasta determinar la causa no se puede garantizar que permanezcan habilitadas.
