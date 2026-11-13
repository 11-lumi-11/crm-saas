# Actividades — CRM SaaS

Microservicio de seguimiento comercial para administrar llamadas, reuniones, correos y tareas por tenant. Permite crear actividades manuales y generar seguimientos a partir de eventos de Oportunidades y Cotizaciones.

## Tecnologías

Python 3.14, AWS Lambda, API Gateway HTTP API, DynamoDB, SNS, SQS y Serverless Framework 4. Utiliza la capa compartida `crm_comun` y el Authorizer JWT del proyecto.

## Endpoints

| Método | Ruta | Función Lambda |
|---|---|---|
| POST | /actividades | CrearActividad |
| GET | /actividades | ListarActividades |
| GET | /actividades/{actividad_id} | ObtenerActividad |
| PUT | /actividades/{actividad_id} | ActualizarActividad |
| PUT | /actividades/{actividad_id}/completar | CompletarActividad |

Todos los endpoints están protegidos. El tenant se obtiene del contexto del Authorizer; las consultas y modificaciones se limitan a ese tenant.

Vendedor, gerente y admin pueden operar dentro de su tenant. Como regla provisional, el vendedor solo puede asignarse actividades a sí mismo al crear y no puede reasignarlas; gerente y admin sí pueden hacerlo.

### Datos y operaciones

Al crear se requieren `tipo`, `titulo`, `cliente_id` y `fecha_programada`. `descripcion`, `oportunidad_id` y `responsable_id` son opcionales; el responsable predeterminado es el usuario autenticado.

- Tipos: `llamada`, `reunion`, `correo`, `tarea`.
- Estados: `pendiente`, `completada`, `cancelada`.
- Origen: `manual` o `automatica`, establecido por el servicio.
- Identificadores con prefijo `act_`; fechas ISO 8601 normalizadas a UTC.

Solo se editan actividades pendientes. Se pueden cancelar mediante actualización; completar requiere la ruta `/completar`. Repetir la finalización devuelve 200 sin generar otro evento. Las actividades completadas o canceladas no se reabren.

El listado admite `responsable_id`, `estado`, `oportunidad_id`, `tipo`, `desde` y `hasta`. Usa `limite` de 1 a 100 (50 por defecto) y cursor `siguiente`, conservando los filtros entre páginas. Responde con `actividades` y `siguiente`; una página filtrada puede estar vacía y tener cursor de continuación.

Las respuestas de error incluyen `codigo` y `mensaje`. Se utilizan 400 para datos inválidos, 401 para contexto de autenticación inválido, 403 para permisos insuficientes, 404 para recursos no encontrados, 409 para conflictos y 503 para errores de infraestructura.

## Modelo DynamoDB

Los nombres físicos llevan el prefijo `<stage>-`. Todas las tablas usan capacidad bajo demanda y pertenecen a Actividades.

| Tabla | Clave | Uso |
|---|---|---|
| t_actividades | tenant_id + actividad_id | Datos de las actividades |
| t_eventos_actividades | evento_id | Outbox de eventos pendientes de publicación |
| t_eventos_recibidos_actividades | tenant_id + evento_id | Deduplicación de eventos recibidos |
| t_oportunidades_control_actividades | tenant_id + oportunidad_id | Estado local de pérdida y progreso de cancelación |

La actividad almacena tipo, título, descripción, cliente, oportunidad opcional, responsable, fecha programada, estado, origen y fechas de creación/actualización. Incluye `version` interna y `evento_origen_id` para actividades automáticas.

Los GSI de actividades usan `tenant_id` con `responsable_id`, `estado`, `oportunidad_id` o `fecha_programada`. El outbox usa `estado-fecha-index` y TTL para eventos enviados. Ejemplos JSON en [modelos/](modelos/).

## Eventos e integraciones

| Evento recibido | Acción |
|---|---|
| oportunidad.etapa_cambiada | Crear seguimiento comercial |
| oportunidad.ganada | Crear tarea de inicio o entrega |
| oportunidad.perdida | Cancelar pendientes de la oportunidad dentro del tenant |
| cotizacion.enviada | Crear seguimiento asignado a creada_por |

`ProcesarEventosActividades` consume una cola SQS propia, suscrita al topic SNS compartido con filtro por tipo y sobre SNS. Incluye DLQ y manejo de errores parciales por lote.

Los eventos se deduplican por tenant e identificador. Una pérdida establece una barrera persistente que impide crear pendientes por eventos tardíos. La cancelación es paginada, conserva progreso y respeta actividades completadas.

**Pendiente para volúmenes grandes:** la cancelación lee las actividades del tenant en páginas. Si no termina en los tres intentos de la cola, el mensaje pasa a la DLQ y pueden quedar actividades pendientes. Esto depende del volumen almacenado, incluso si los datos se cargaron directamente con Python. Para la demo, comprobar en AWS que se cancelen las actividades de una oportunidad perdida y revisar la DLQ si no ocurre. El cursor guardado permite continuar el recorrido al reprocesar el mensaje; verificar el resultado antes de darlo por resuelto.

**Solución propuesta:** convertir la cancelación en un trabajo por lotes con una continuación durable: guardar el progreso y asegurar que exista una siguiente ejecución hasta completar el recorrido, reservando la DLQ para fallos reales. La solución debe conservar la barrera ante eventos tardíos, admitir mensajes duplicados y probarse con volumen y concurrencia. Un índice por oportunidad puede reducir lecturas, pero su consistencia eventual debe considerarse antes de reemplazar el recorrido actual de lectura consistente. Aumentar los reintentos o el tiempo solo mitigaría el problema, sin eliminarlo.

Al completar se guardan el cambio y `actividad.completada` en una transacción. El evento contiene `actividad_id`, `oportunidad_id` (vacío si no aplica) y `responsable_id` de la actividad, destinatario utilizado por Notificaciones.

El publicador común procesa el outbox cada minuto y publica con el atributo SNS `tipo`. La entrega es al menos una vez y no garantiza orden global. El servicio utiliza identificadores y eventos; no consulta tablas de otros microservicios.

## Configuración

`serverless.yml` define recursos en `us-east-1`, utiliza `LabRole` e importa `CapaComunArn`, `AuthorizerArn` y `EventosTopicArn` de `crm-compartido` en el mismo stage.

Las variables `TABLE_ACTIVIDADES`, `TABLE_EVENTOS`, `TABLE_RECIBIDOS` y `TABLE_OPORTUNIDADES_CONTROL` identifican las tablas propias. `INDEX_RESPONSABLE`, `INDEX_ESTADO`, `INDEX_OPORTUNIDAD` e `INDEX_FECHA` identifican los GSI; `SNS_TOPIC_ARN` referencia el topic compartido.

| Variable de plazo | Valor predeterminado |
|---|---|
| DIAS_SEGUIMIENTO_ETAPA | 1 día |
| DIAS_INICIO_SERVICIO | 1 día |
| DIAS_SEGUIMIENTO_COTIZACION | 3 días |

Los plazos admiten enteros de 0 a 365 y se calculan desde la fecha del evento. Los valores predeterminados y la asignación al creador de la cotización son decisiones provisionales.

El paquete Lambda incluye únicamente `src/**/*.py`. `crm_comun` proviene de la capa; boto3 y botocore, del runtime. Pruebas, documentación y herramientas de desarrollo quedan excluidas.

## Pruebas locales

Desde la raíz del repositorio, con Python 3.10 o superior:

```sh
python3 -m venv /tmp/crm-actividades-venv
/tmp/crm-actividades-venv/bin/python -m pip install -r servicios/actividades/requirements-dev.txt
PYTHONDONTWRITEBYTECODE=1 /tmp/crm-actividades-venv/bin/python -m pytest -q -p no:cacheprovider servicios/actividades/tests
```

Resultado verificado: **56 pruebas aprobadas con Python 3.12.14**, utilizando Moto y credenciales ficticias, sin llamadas reales a AWS. Cubren endpoints, permisos, aislamiento, paginación, transacciones, eventos, duplicados, reintentos y contratos con los servicios existentes. También verifican YAML, referencias e importaciones desde un ZIP local de comprobación.

Colección independiente en [postman/Actividades.postman_collection.json](postman/Actividades.postman_collection.json). Requiere un adaptador HTTP local con autorización o un API Gateway desplegado; no incluye servidor HTTP local.

## Estado y despliegue

**Despliegue y validación AWS pendientes.** El ZIP de comprobación no sustituye el empaquetado oficial de Serverless. Quedan pendientes la ejecución en Python 3.14, permisos, API Gateway, programación del publicador y comportamiento real SNS/SQS/DLQ.

El despliegue requiere el stack compartido, identidades activas de Usuarios y el mismo stage. Desde esta carpeta, el comando previsto es `serverless deploy --stage dev`.

La carga de 30000 registros se integrará con el generador común, distribuidos entre tres tenants y con referencias coherentes a usuarios, clientes y oportunidades del mismo tenant. Los registros deberán incluir `version: 1`; la carga masiva todavía está pendiente.
