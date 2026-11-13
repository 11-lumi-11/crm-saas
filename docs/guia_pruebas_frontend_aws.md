# Guía de pruebas del frontend y seguimiento en AWS

Esta guía permite ejecutar los flujos principales desde el frontend y comprobar qué ocurrió en los servicios de AWS. Está preparada para el despliegue **`dev`**, región **`us-east-1`**, en la cuenta de AWS utilizada por el proyecto el 2026-11-12.

**Frontend:** [Abrir NodoCRM en Amplify](https://dev.d38c15mc7g1yzr.amplifyapp.com).

La guía describe resultados esperados; no significa que todas las pruebas estén aprobadas. En particular, la aceptación de una cotización cuya oportunidad está perdida sigue pendiente de comprobación real. Anota al final qué ejecutaste y su resultado.

## 1. Preparación

1. Abre el frontend y la [consola de AWS](https://console.aws.amazon.com/) en pestañas distintas. En AWS selecciona **Norte de Virginia (`us-east-1`)** y la cuenta donde desplegaste el proyecto.
2. Utiliza una empresa de prueba y un usuario **admin**. Para probar permisos y avisos por rol necesitarás también un vendedor y, opcionalmente, un gerente del mismo tenant.
3. Usa nombres que puedas reconocer, por ejemplo `Prueba cliente 12nov`, `Prueba oportunidad 12nov` y `Prueba producto 12nov`. Si repites la guía, utiliza nombres o sufijos diferentes.
4. Conserva los identificadores que encuentres en DynamoDB para relacionar los registros:

   | Dato | Valor de esta prueba |
   | --- | --- |
   | `tenant_id` | |
   | `usuario_id` administrador | |
   | `cliente_id` | |
   | `oportunidad_id` | |
   | `actividad_id` | |
   | `producto_id` | |
   | `cotizacion_id` | |
   | `solicitud_aceptacion_id` | |
   | `evento_id` de interés | |

5. Las operaciones crean o modifican **datos reales** del entorno `dev`. En particular, archivar un cliente lo oculta y conserva sus contactos; actualmente **no existe una opción de restauración**. Usa datos de prueba y deja para el final el archivo.

Los indicadores de la sección **Inicio** todavía usan datos de demostración. Para esta guía utiliza las pantallas de Clientes, Oportunidades, Actividades, Productos, Cotizaciones y Notificaciones.

## 2. Cómo encontrar evidencias en la consola

### DynamoDB: registros y eventos

1. En AWS, abre **DynamoDB → Tables / Tablas** y selecciona la tabla indicada en cada paso.
2. Entra en **Explore table items / Explorar elementos**. Para las tablas de negocio cuya clave empieza por `tenant_id`, puedes seleccionar **Query** y usar el `tenant_id` de tu empresa; si también conoces la clave de ordenación, introduce su ID exacto.
3. Si buscas por un campo que no es clave —por ejemplo, `nombre`— utiliza **Scan / Explorar** con un filtro o el índice que corresponda. La búsqueda puede requerir varias páginas; en un entorno con muchos datos, Scan lee más registros. [Cómo consultar elementos en DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/getting-started-step-5.html).
4. En las tablas de eventos, la clave principal es `evento_id`. Si no lo conoces, usa Scan y filtra por `tenant_id`; abre los elementos para revisar `evento.tipo` y `evento.datos`. El campo `estado` que interesa al publicador está **fuera** del mapa `evento`.

> **Qué es el outbox:** cada servicio que publica eventos guarda primero el cambio y un registro del evento en su propia tabla `dev-t_eventos_...`. Un publicador lo envía a SNS aproximadamente cada minuto. `estado: pendiente` indica que todavía debe enviarse; `estado: enviado` indica que el publicador recibió una respuesta exitosa de SNS y lo marcó como enviado. Esto **no prueba por sí solo** que una cola lo haya procesado.
>
> Los eventos enviados tienen un TTL de siete días; DynamoDB puede eliminarlos después de ese plazo. Los pendientes no llevan ese TTL. Como la publicación es asíncrona, puede que nunca alcances a ver el estado `pendiente`.

### SNS: tema y métricas

1. Abre **Amazon SNS → Topics / Temas → `dev-eventos-crm-topic`**.
2. En **Subscriptions / Suscripciones**, revisa las suscripciones SQS y sus filtros por atributo `tipo`. El tema distribuye copias a los servicios interesados; una suscripción puede ignorar un evento cuyo tipo no esté en su filtro.
3. En **Monitoring / Monitoreo** o en **CloudWatch → Metrics → SNS → Topic Metrics**, puedes revisar `NumberOfMessagesPublished` y `NumberOfNotificationsDelivered` alrededor de la hora de la prueba. Son **contadores agregados**, no identifican por sí solos el `evento_id` de tu operación. Las métricas pueden tardar en aparecer. [Métricas de SNS](https://docs.aws.amazon.com/sns/latest/dg/sns-monitoring-using-cloudwatch.html).

**No esperes una bandeja histórica de mensajes en el tema SNS.** Para demostrar un evento concreto, relaciona el registro del outbox y su `evento_id` con los datos y efectos del consumidor. Los logs de entrega específicos de SNS solo estarán disponibles si se configuraron; el repositorio no acredita que estén activados.

### SQS: colas y colas de errores

1. Abre **Amazon SQS → Queues / Colas** y busca el nombre indicado.
2. Observa sus métricas y el número aproximado de mensajes disponibles o en proceso, así como su DLQ —la cola a la que pueden llegar los mensajes después de agotar los intentos—.
3. **Una cola vacía no demuestra que falló:** Lambda puede recibir y procesar el mensaje muy rápido. En cambio, una DLQ con mensajes merece revisión; anota la hora y conserva la evidencia.

Durante una prueba normal no es necesario pulsar **Poll for messages**, borrar ni reenviar mensajes. Recibir un mensaje desde la consola puede volverlo temporalmente invisible para otros consumidores y alterar la observación. [Visibilidad de mensajes SQS](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html).

### CloudWatch y Lambda: ejecución y errores

- Abre **CloudWatch → Log groups / Grupos de registro** y busca `/aws/lambda/<nombre-función>`. También puedes entrar en **Lambda → Functions → función → Monitor → View CloudWatch logs**.
- Selecciona el periodo de la prueba y revisa los flujos de registro más recientes. Una invocación demuestra que se ejecutó la función, pero no necesariamente que el dato de negocio sea correcto: contrástala con DynamoDB.
- Los consumidores de aceptación no registran necesariamente el contenido o el motivo de cada error en sus logs; una ejecución sin detalles no demuestra que el mensaje se haya procesado. Revisa estado final, outbox y DLQ.
- No todas las funciones incluyen el `evento_id` en sus logs. Cuando no aparezca, relaciona la evidencia mediante las tablas, el horario y los identificadores de negocio. No copies contraseñas, JWT, credenciales ni datos personales en capturas.

## 3. Mapa rápido de recursos

### DynamoDB

| Para revisar | Tabla en `dev` | Claves útiles |
| --- | --- | --- |
| Empresas | `dev-t_tenants` | `tenant_id` |
| Usuarios | `dev-t_usuarios` | `tenant_id` + `usuario_id` |
| Reserva de nombre / correo | `dev-t_tenants_locks`, `dev-t_correos_locks` | `nombre_normalizado` / `correo` |
| Clientes y contactos | `dev-t_clientes`, `dev-t_contactos` | `tenant_id` + ID de la entidad |
| Oportunidades e historial | `dev-t_oportunidades`, `dev-t_historial_etapas` | `tenant_id` + `oportunidad_id` / `historial_id`; el historial incluye `oportunidad_id` |
| Actividades | `dev-t_actividades` | `tenant_id` + `actividad_id`; contiene `oportunidad_id` y, si es automática, `evento_origen_id` |
| Deduplicación y control de Actividades | `dev-t_eventos_recibidos_actividades`, `dev-t_oportunidades_control_actividades` | `tenant_id` + `evento_id` / `oportunidad_id` |
| Productos y cotizaciones | `dev-t_productos`, `dev-t_cotizaciones` | `tenant_id` + `producto_id` / `cotizacion_id` |
| Decisión de aceptación | `dev-t_solicitudes_aceptacion` | `tenant_id` + `solicitud_id` |
| Notificaciones y lecturas | `dev-t_notificaciones`, `dev-t_lecturas_notificaciones` | `tenant_id` + `notificacion_id` / `lectura_id` |
| Outboxes | `dev-t_eventos_usuarios`, `dev-t_eventos_clientes`, `dev-t_eventos_oportunidades`, `dev-t_eventos_actividades`, `dev-t_eventos_productos_cotizaciones` | `evento_id`; cada evento incluye `tenant_id`, `evento.tipo` y `evento.datos` |

### SQS y funciones consumidoras

| Uso | Cola principal | DLQ | Lambda consumidora |
| --- | --- | --- | --- |
| Avisos | `dev-notificaciones` | `dev-notificaciones-dlq` | `crm-notificaciones-dev-procesarEventos` |
| Seguimientos y cancelaciones | `dev-actividades` | `dev-actividades-dlq` | `crm-actividades-dev-procesarEventosActividades` |
| Solicitud de aceptación de cotización | `crm-oportunidades-dev-ColaSolicitudAceptacion-hVGkaPrgl25g` | `crm-oportunidades-dev-ColaSolicitudAceptacionDLQ-6sY06hBRRkrb` | `crm-oportunidades-dev-procesarSolicitudAceptacion` |
| Resultado de aceptación para Cotizaciones | `crm-productos-cotizaciones-dev-ColaResultadoAceptacion-MSkFc1tIUVS3` | `crm-productos-cotizaciones-dev-ColaResultadoAceptacionDLQ-KtVFaPpYQeor` | `crm-productos-cotizaciones-dev-procesarResultadoAceptacion` |
| Consumidor anterior de `cotizacion.aceptada` | `dev-oportunidades-cotizacion-aceptada` | `dev-oportunidades-cotizacion-aceptada-dlq` | `crm-oportunidades-dev-procesarCotizacionAceptada` |

Los dos pares de colas con nombres largos fueron consultados en CloudFormation para el despliegue actual; pueden cambiar si sus recursos se reemplazan. Si no los encuentras, abre **CloudFormation → Stacks → `crm-oportunidades-dev` o `crm-productos-cotizaciones-dev` → Resources**, busca `ColaSolicitudAceptacion`, `ColaSolicitudAceptacionDLQ`, `ColaResultadoAceptacion` o `ColaResultadoAceptacionDLQ` y consulta su **Physical ID**.

Los publicadores programados se llaman `crm-usuarios-dev-publicarEventos`, `crm-clientes-dev-publicarEventos`, `crm-oportunidades-dev-publicarEventos`, `crm-actividades-dev-publicarEventos` y `crm-productos-cotizaciones-dev-publicarEventos`. Sus grupos de CloudWatch tienen el prefijo `/aws/lambda/`.

## 4. Flujo A: registrar empresa e iniciar sesión

Si ya cuentas con una empresa de prueba, puedes iniciar sesión y comenzar en el flujo B. Si quieres probar el alta, usa un **nombre de empresa y correo nuevos**.

### En el frontend

1. En la página de acceso selecciona **Registrar empresa**.
2. Completa empresa, rubro, nombre del administrador, correo y contraseña. Envía el formulario.
3. La aplicación debe indicar que la empresa fue creada y pedir que inicies sesión. Ingresa con las credenciales recién creadas.
4. Recarga la página: la sesión debe permanecer mientras el token sea válido. Cierra sesión y comprueba que vuelva a solicitar el acceso; luego ingresa nuevamente para continuar.

Si el login falla inmediatamente después del alta, espera unos segundos y reintenta: el índice de correo se actualiza de forma asíncrona.

### En AWS

1. En **DynamoDB → `dev-t_tenants`**, busca el nombre de empresa y anota su `tenant_id`.
2. En **`dev-t_usuarios`**, consulta por ese `tenant_id`: debe existir el administrador con `rol: admin` y `estado: activo`. Anota su `usuario_id`. No incluyas el hash ni el correo en capturas compartidas.
3. Opcionalmente comprueba los candados en **`dev-t_tenants_locks`** y **`dev-t_correos_locks`**.
4. En **`dev-t_eventos_usuarios`**, localiza por `tenant_id` el evento cuyo `evento.tipo` es `usuario.creado`. Anota el `evento_id` y comprueba después si quedó `enviado`.
5. En **`dev-t_notificaciones`**, busca un aviso del mismo tenant con ese `evento_id` y destino del administrador. En el frontend, revisa **Notificaciones** y usa **Actualizar** después de esperar.
6. Si no aparece, revisa `crm-usuarios-dev-publicarEventos`, el tema SNS, `dev-notificaciones`, su DLQ y `crm-notificaciones-dev-procesarEventos`.

**Resultado esperado:** empresa y admin existen; el login funciona y el aviso de bienvenida llega de forma diferida. Si no aparece el aviso pero el usuario existe, registra por separado ambos resultados.

## 5. Flujo B: crear cliente y contacto

### En el frontend

1. Entra como admin en **Clientes → Nuevo cliente**.
2. Crea una empresa de prueba con nombre reconocible y guarda. La persona autenticada queda como responsable si no se indica otro.
3. Abre el cliente y agrega un contacto. Si quieres, marca **Contacto principal**.
4. Recarga la página y vuelve a consultar el cliente y su contacto.

### En AWS

1. En **`dev-t_clientes`**, consulta por `tenant_id` y busca el nombre. Anota `cliente_id`; revisa `nombre`, `tipo`, `estado` y `responsable_id`.
2. En **`dev-t_contactos`**, busca el contacto con el mismo `tenant_id` y `cliente_id`. Si lo creaste como principal, debe tener `es_principal: true` y el cliente debe tener `contacto_principal_id` igual al `contacto_id`.
3. En **`dev-t_eventos_clientes`**, encuentra `evento.tipo: cliente.creado` cuyo `evento.datos.cliente_id` coincida. Anota `evento_id`; luego comprueba `estado: enviado`.
4. En **SNS → `dev-eventos-crm-topic`**, revisa la suscripción de **Notificaciones** y las métricas generales. En **SQS**, revisa `dev-notificaciones` y, si hay problemas, `dev-notificaciones-dlq`.
5. En **`dev-t_notificaciones`**, busca `tenant_id` + `evento_id`. El destinatario esperado es `responsable_id`. Comprueba el aviso también en el frontend.
6. En CloudWatch, si hace falta, revisa `crm-clientes-dev-crearCliente`, `crm-clientes-dev-publicarEventos` y `crm-notificaciones-dev-procesarEventos`.

**Resultado esperado:** cliente y contacto persisten; llega el aviso de cliente creado. **Crear un contacto no publica un evento en la implementación actual**, así que no esperes uno por ese paso.

## 6. Flujo C: crear oportunidad y generar un seguimiento automático

### C1. Crear oportunidad

1. En el frontend abre **Oportunidades → Nueva oportunidad**.
2. Selecciona el cliente del flujo B, escribe un título reconocible y un monto, y guarda.
3. La tarjeta debe aparecer en etapa **nueva**. Si no aparece inmediatamente, pulsa **Actualizar**.

**En AWS:**

1. En **`dev-t_oportunidades`**, consulta por `tenant_id`, encuentra el título y anota `oportunidad_id`. Comprueba `cliente_id`, `etapa: nueva`, `monto_estimado` y `responsable_id`.
2. En **`dev-t_eventos_oportunidades`**, busca `evento.tipo: oportunidad.creada` y el mismo `evento.datos.oportunidad_id`; anota su `evento_id` y comprueba que se envíe.
3. En **`dev-t_notificaciones`**, busca ese `evento_id`; el responsable debe recibir el aviso.
4. En **SNS**, el tipo `oportunidad.creada` está dirigido a Notificaciones. **La creación por sí sola no debe crear una actividad automática**; esta se genera en el cambio de etapa del paso siguiente.

### C2. Cambiar etapa y verificar Actividades

1. En el frontend abre la tarjeta y pulsa **Avanzar a calificada**.
2. Comprueba que la tarjeta pase a **calificada**. Abre nuevamente su detalle y consulta el historial; si tarda, usa **Actualizar historial**.
3. Ve a **Actividades**, espera y pulsa **Actualizar**. Debe aparecer una tarea automática llamada **Seguimiento comercial**. Copia o localiza su `actividad_id` en DynamoDB.

**En AWS:**

1. En **`dev-t_oportunidades`**, la misma oportunidad debe tener `etapa: calificada`.
2. En **`dev-t_historial_etapas`**, busca por `tenant_id` y `oportunidad_id` o usa `oportunidad_id-index`: debe haber una fila de `nueva` a `calificada`, con el usuario que hizo el cambio.
3. En **`dev-t_eventos_oportunidades`**, encuentra el evento `oportunidad.etapa_cambiada` de esa oportunidad y anota su `evento_id`.
4. En **SNS → tema `dev-eventos-crm-topic`**, revisa que las suscripciones de `dev-actividades` y `dev-notificaciones` incluyan ese tipo. En **SQS**, consulta métricas de ambas colas y, ante problemas, sus DLQ.
5. En **`dev-t_eventos_recibidos_actividades`**, busca `tenant_id` + ese `evento_id`. Si existe, Actividades registró el procesamiento del evento.
6. En **`dev-t_actividades`**, busca por tenant y oportunidad: la tarea debe tener `origen: automatica`, `estado: pendiente` y `evento_origen_id` igual al `evento_id` del cambio de etapa.
7. En **`dev-t_notificaciones`**, busca el mismo `evento_id` para confirmar el aviso de cambio de etapa. Revisa la pantalla **Notificaciones**.
8. Ante problemas, revisa los logs de `crm-oportunidades-dev-cambiarEtapa`, `crm-oportunidades-dev-publicarEventos`, `crm-actividades-dev-procesarEventosActividades` y `crm-notificaciones-dev-procesarEventos`.

**Resultado esperado:** la oportunidad, su historial, la tarea y el aviso corresponden a la misma operación. Las tablas de Actividades y Notificaciones pueden actualizarse unos minutos después del cambio.

## 7. Flujo D: completar una actividad y leer un aviso

### En el frontend

1. En **Actividades**, busca el seguimiento generado en el flujo C y pulsa **Completar**.
2. Comprueba que quede **completada**; recarga y verifica que conserve el estado.
3. Espera y entra en **Notificaciones**. Busca el aviso de actividad completada; pulsa **Marcar leída** y recarga para verificar que conserve la lectura.

### En AWS

1. En **`dev-t_actividades`**, consulta `tenant_id` + `actividad_id`: debe tener `estado: completada`.
2. En **`dev-t_eventos_actividades`**, busca `evento.tipo: actividad.completada` y el mismo `evento.datos.actividad_id`. Anota `evento_id` y comprueba que se haya enviado.
3. En **SNS**, ese evento se distribuye a Notificaciones. Revisa **`dev-notificaciones`**, su DLQ y la Lambda `crm-notificaciones-dev-procesarEventos` si el aviso no llega.
4. En **`dev-t_notificaciones`**, encuentra el aviso por `tenant_id` + `evento_id`; anota `notificacion_id`.
5. En **`dev-t_lecturas_notificaciones`**, consulta el mismo `tenant_id` y `lectura_id` con el formato `<notificacion_id>#<usuario_id>`. Debe existir una fila para el usuario que marcó el aviso. La lectura es individual incluso cuando un aviso se dirige a un rol.

**Resultado esperado:** la actividad persiste completada y el aviso queda leído para ese usuario. La pantalla muestra hasta una página por vez; usa **Cargar más notificaciones** si no encuentras el aviso.

## 8. Flujo E: producto, cotización y venta ganada

Este flujo debe hacerse con una **oportunidad abierta**. Si la del flujo C sigue en `calificada`, puedes reutilizarla. Si está cerrada, crea otra. Utiliza admin o gerente para crear el producto.

### E1. Crear producto y borrador

1. En **Productos → Nuevo producto**, crea un producto activo, por ejemplo `Prueba servicio 12nov`, precio `250`, moneda `PEN`.
2. En **Cotizaciones → Nueva cotización**, selecciona la oportunidad abierta y agrega dos unidades del producto. Guarda el borrador.
3. Comprueba que el total sea `500 PEN`; el total definitivo lo calcula el backend.

**En AWS:**

1. En **`dev-t_productos`**, busca por `tenant_id` y nombre; anota `producto_id` y revisa `precio`, `moneda` y `estado`.
2. En **`dev-t_cotizaciones`**, busca el borrador por `tenant_id` y `oportunidad_id`; anota `cotizacion_id`. Comprueba `estado: borrador`, `cliente_id`, `oportunidad_id`, el producto en `items`, cantidad y `total`.
3. Crear producto y crear borrador **no publican eventos** en esta implementación. No esperes una notificación por esas dos acciones.

### E2. Enviar cotización

1. En el frontend pulsa **Enviar** en el borrador.
2. En **`dev-t_cotizaciones`**, comprueba `estado: enviada` y `fecha_envio`.
3. En **`dev-t_eventos_productos_cotizaciones`**, busca `evento.tipo: cotizacion.enviada` con el `cotizacion_id`; anota su `evento_id` y revisa que quede enviado.
4. En **`dev-t_actividades`**, espera una tarea automática **Seguimiento de cotización** para esa oportunidad; `evento_origen_id` debe coincidir con el evento enviado. El responsable es quien creó la cotización.
5. En **`dev-t_notificaciones`**, busca el aviso de ese evento, dirigido a `creada_por`. Revisa también el frontend. Las colas implicadas son `dev-actividades` y `dev-notificaciones`.

### E3. Solicitar y confirmar aceptación

1. En el frontend pulsa **Aceptar** una sola vez. Debe aparecer **aceptacion pendiente**; esa respuesta aún no significa que terminó el proceso.
2. Espera la actualización automática. Puede tardar varios minutos porque intervienen publicadores de más de un servicio.
3. Al finalizar, la cotización debe quedar **aceptada**. En **Oportunidades**, actualiza y comprueba que la oportunidad quede **ganada**.

**Sigue la cadena en AWS:**

1. **Cotizaciones:** en `dev-t_cotizaciones` comprueba `solicitud_aceptacion_id` y anótalo. Durante el proceso puede verse `estado: aceptacion_pendiente`. En `dev-t_eventos_productos_cotizaciones` busca `cotizacion.aceptacion_solicitada` con ese `solicitud_id` y el `cotizacion_id`.
2. **SNS → Oportunidades:** en el tema `dev-eventos-crm-topic` localiza la suscripción a la cola `crm-oportunidades-dev-ColaSolicitudAceptacion-hVGkaPrgl25g`. Revisa su DLQ si el procesamiento no continúa. La Lambda es `crm-oportunidades-dev-procesarSolicitudAceptacion`.
3. **Decisión y venta:** en `dev-t_solicitudes_aceptacion`, consulta `tenant_id` + `solicitud_id`; `resultado` debe ser `oportunidad.aceptacion_confirmada`. En `dev-t_oportunidades`, la oportunidad debe estar `ganada`; en `dev-t_historial_etapas`, busca el cambio a `ganada` con `usuario_id: sistema`.
4. **Outbox de Oportunidades:** en `dev-t_eventos_oportunidades`, busca los eventos `oportunidad.aceptacion_confirmada` —con el mismo `solicitud_id`— y `oportunidad.ganada` —con el mismo `oportunidad_id`—. Anota sus `evento_id`.
5. **SNS → Cotizaciones:** revisa la cola `crm-productos-cotizaciones-dev-ColaResultadoAceptacion-MSkFc1tIUVS3` y su DLQ. La Lambda consumidora es `crm-productos-cotizaciones-dev-procesarResultadoAceptacion`.
6. **Resultado final:** en `dev-t_cotizaciones`, comprueba `estado: aceptada`, `resultado_solicitud_id` igual a `solicitud_aceptacion_id` y `fecha_respuesta`. En `dev-t_eventos_productos_cotizaciones`, busca `cotizacion.aceptada` para esa cotización.
7. **Efectos posteriores:** `oportunidad.ganada` puede crear la tarea automática **Iniciar servicio o entrega** en `dev-t_actividades`. Notificaciones genera avisos para el responsable y para el rol gerente. `cotizacion.aceptada` genera otro aviso para el rol gerente; un admin no lo ve solo por ser admin. Comprueba el aviso con un gerente del mismo tenant si deseas probar ese destino.
8. El consumidor anterior de `cotizacion.aceptada` también tiene suscripción y cola propias; cuando recibe el evento del flujo nuevo, la oportunidad ya debería estar cerrada. No publiques manualmente ese evento para simular la aceptación.

**Resultado esperado:** una sola oportunidad ganada y la cotización aceptada después de la decisión. La presencia del mensaje en una cola durante la observación no es obligatoria; busca la decisión, el historial y los estados finales.

## 9. Flujo F: oportunidad perdida y aceptación denegada

Este caso aún está **pendiente de validación real**. Usa una oportunidad nueva de prueba; una oportunidad cerrada no se puede reabrir desde la interfaz.

1. Crea una oportunidad abierta para el cliente de prueba.
2. Crea y **envía** una cotización para esa oportunidad mientras está abierta. El formulario solo ofrece oportunidades abiertas.
3. Opcional: avanza la oportunidad a **calificada** y espera que se cree una actividad pendiente. Así podrás observar su cancelación.
4. En Oportunidades, abre la tarjeta y selecciona **Marcar perdida**. Introduce un motivo y confirma.
5. En **`dev-t_oportunidades`**, comprueba `etapa: perdida` y `motivo_perdida`. En **`dev-t_historial_etapas`**, revisa la transición. En **`dev-t_eventos_oportunidades`**, busca `oportunidad.perdida`.
6. En **`dev-t_oportunidades_control_actividades`**, busca `tenant_id` + `oportunidad_id`; tras procesar el evento debe figurar `perdida: true`. En **`dev-t_actividades`**, las tareas que estaban **pendientes** para esa oportunidad deben pasar a `cancelada`; las que ya estaban completadas se conservan. Revisa `dev-actividades` y su DLQ si no ocurre.
7. En Cotizaciones, solicita **Aceptar** en la cotización ya enviada. Primero puede mostrarse `aceptacion_pendiente`. Espera la decisión: debe volver a **enviada** con un mensaje que indique que la oportunidad está perdida.
8. En **`dev-t_cotizaciones`**, anota `solicitud_aceptacion_id`; revisa que `resultado_solicitud_id` coincida y que `resultado_aceptacion` contenga el motivo. En **`dev-t_solicitudes_aceptacion`**, consulta esa solicitud y comprueba `resultado: oportunidad.aceptacion_rechazada`.
9. En **`dev-t_eventos_oportunidades`**, busca `oportunidad.aceptacion_rechazada` con ese `solicitud_id`. La oportunidad debe seguir perdida. Para esta solicitud rechazada no debe generarse `cotizacion.aceptada`; distingue la solicitud y la cotización de otras pruebas anteriores.

**Límite conocido:** con muchos registros de Actividades, la cancelación podría agotar los intentos y quedar en la DLQ; está documentado como pendiente. Con pocos datos de demo también debe verificarse el resultado real.

## 10. Flujo G: aislamiento, permisos y archivo

### Aislamiento entre empresas

1. Con una segunda empresa y otro usuario, inicia sesión y consulta Clientes y Oportunidades.
2. Comprueba que no aparecen los registros de la primera empresa. En DynamoDB, identifica los `tenant_id` de ambos y verifica que cada registro pertenece al tenant esperado.
3. Esta prueba de interfaz no cubre por sí sola intentar acceder directamente a un ID de otra empresa; registra por separado si se comprueba esa respuesta desde la API.

### Permisos de vendedor

1. Inicia sesión con un vendedor del tenant de prueba. En **Productos**, no debe ofrecerse el botón de creación o edición para ese rol.
2. En **Clientes**, el vendedor no debe ver la acción de archivar. Comprueba además las acciones que sí están permitidas en la matriz de roles.
3. Que un botón esté oculto comprueba la interfaz, no la autorización del backend. La respuesta de la API ante una petición directa con token de vendedor se debe validar por separado si se necesita esa evidencia.

### Archivo de cliente — ejecutar al final

1. Como admin o gerente, archiva el cliente de prueba desde su ficha. Debe desaparecer del listado normal.
2. En **`dev-t_clientes`**, busca el registro por `tenant_id` + `cliente_id`: debe conservarse con `eliminado: true`, `estado: inactivo` y `fecha_eliminacion`.
3. En **`dev-t_contactos`**, confirma que los contactos siguen guardados. No hay evento de eliminación, no se eliminan automáticamente oportunidades ni se restauran desde la interfaz actual.

## 11. Si algo no ocurre

| Síntoma | Revisión sugerida |
| --- | --- |
| La aplicación no abre | **Amplify → aplicación `crm-frontend-dev` → rama `dev`**: revisar el último trabajo. Abrir la URL del inicio de esta guía. |
| No inicia sesión o una acción devuelve error | Revisar el mensaje en pantalla y la Lambda correspondiente en CloudWatch. Si el token venció, volver a iniciar sesión. Confirmar cuenta, región y `tenant_id`. |
| La fila existe pero no llega un aviso | Buscar el evento correspondiente en el outbox del productor; comprobar `estado`, luego tema SNS, `dev-notificaciones`, DLQ y logs del consumidor. |
| No aparece la tarea automática | Buscar `oportunidad.etapa_cambiada` o `cotizacion.enviada` en el outbox; comparar `evento_id` con `dev-t_eventos_recibidos_actividades` y `evento_origen_id` en la actividad. Revisar `dev-actividades-dlq`. |
| Aceptación pendiente durante varios minutos | Revisar `dev-t_eventos_productos_cotizaciones`, la cola de solicitud y su DLQ, `dev-t_solicitudes_aceptacion`, `dev-t_eventos_oportunidades`, la cola de resultado y su DLQ, y los logs de ambos consumidores. |
| El mensaje no aparece en SNS o SQS | SNS no ofrece una bandeja histórica y SQS puede quedar vacía tras el consumo. Usar el outbox, las métricas agregadas y el estado de negocio como evidencias complementarias. |

No reproceses ni elimines mensajes de una DLQ sin revisar primero qué operación representan y cómo afecta su reentrega. Guarda la evidencia sin secretos ni datos personales.

## 12. Registro de resultados

| Fecha y hora | Responsable | Cuenta / stage / región | Flujo y datos de prueba | Resultado | Evidencia o incidencia |
| --- | --- | --- | --- | --- | --- |
| | | `dev` / `us-east-1` | | Pendiente | |

Al terminar, actualiza la matriz de [validación AWS del documento base](documento_base.md#14-validación-pendientes-y-evidencia-aws) con lo observado. Un despliegue exitoso o un HTTP 200 de la página no sustituyen estas pruebas.
