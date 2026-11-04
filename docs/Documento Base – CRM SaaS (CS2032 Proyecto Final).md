# Documento Base – CRM SaaS

*CS2032 Cloud Computing · Proyecto Final · Ciclo 2026-2*

> **Estado:** borrador para revisión del grupo. Todo lo marcado como **\[CONFIRMAR\]** es una propuesta que el grupo debe aprobar antes de empezar a programar. Una vez aprobado, este documento es la **única fuente de verdad**: si algo cambia, se cambia aquí primero y se avisa al grupo.

## 1. Para qué sirve este documento

Este documento sirve para organizarnos mejor y evitar confusiones, de modo que todos podamos trabajar en paralelo. Responde, para todo el grupo y sin tecnicismos innecesarios:

- Qué es la aplicación y quién la usa.
- Qué microservicios existen, qué hace cada uno y qué **no** hace.
- Qué datos guarda cada uno, con nombres exactos.
- Cómo se avisan entre sí (eventos).
- Qué reglas de nombres seguimos.
- Quién es responsable de qué.

## 2. De qué trata la aplicación

Es un **CRM (Customer Relationship Management) como servicio (SaaS)**. Una empresa lo contrata para organizar sus ventas: registrar a sus clientes, seguir sus oportunidades de venta, programar tareas de seguimiento, armar cotizaciones y recibir avisos.

La misma aplicación atiende a **varias empresas a la vez** (multi-tenancy), cada una con sus datos totalmente separados.

### Glosario (para no confundirnos)

| Término | Significado | Ejemplo |
| --- | --- | --- |
| **Tenant** | La empresa que contrata nuestro CRM | Seguros Andinos |
| **Usuario** | Persona que trabaja en un tenant y entra al sistema | Marta, vendedora de Seguros Andinos |
| **Cliente** (o cuenta) | Empresa o persona a la que el tenant le vende. Es un dato dentro del CRM, **no usa nuestro sistema** | Constructora Andes |
| **Contacto** | Persona concreta dentro de un cliente | Ana, gerente de compras de Constructora Andes |
| **Oportunidad** | Una posible venta a un cliente, con etapa y monto | Seguro de flota por S/ 80,000 |
| **Actividad** | Tarea de seguimiento: llamada, reunión, correo, tarea | Llamar a Ana el viernes |
| **Producto** | Algo que el tenant vende | Seguro vehicular básico |
| **Cotización** | Oferta formal de productos para una oportunidad | Cotización #123 con 10 vehículos |
| **Evento** | Aviso interno de que algo ocurrió | "Oportunidad ganada" |
| **Rol** | Qué puede hacer un usuario | admin, gerente, vendedor |

> **Regla de oro:** en el informe y la exposición, "tenant" es siempre la empresa que usa el CRM y "cliente" es siempre un registro dentro del CRM. Nunca mezclar.

## 3. Tenants de prueba (demo y datos ficticios)

Son 3 tenants. La demo se hace con 2 de ellos.

| tenant\_id | Nombre | Rubro |
| --- | --- | --- |
| `ten_seguros` | Seguros Andinos | Seguros |
| `ten_electro` | ElectroHogar | Venta de electrodomésticos |
| `ten_consultora` | SoftNova Consultores | Consultoría de software |

**\[CONFIRMAR\]** Demo con `ten_seguros` y `ten_electro`.

## 4. Visión general de microservicios

| # | Microservicio | Qué hace en una frase | Responsable |
| --- | --- | --- | --- |
| 1 | **Usuarios y Tenants** | Registra empresas y usuarios, hace el login y emite el token | *(por asignar)* |
| 2 | **Clientes** | Guarda cuentas y sus contactos | *(por asignar)* |
| 3 | **Oportunidades** | Gestiona el pipeline de ventas y sus etapas | *(por asignar)* |
| 4 | **Actividades** | Gestiona tareas de seguimiento | *(por asignar)* |
| 5 | **Productos y Cotizaciones** | Catálogo y cotizaciones | *(por asignar)* |
| 6 | **Notificaciones** | Escucha eventos y guarda avisos para los usuarios | *(por asignar)* |

Otras piezas del grupo: **FrontEnd (Amplify)**, **Diagrama de arquitectura**, **Generación de datos ficticios**, **Informe y presentación**.

### Principios que valen para todos

1. **Cada microservicio tiene su propia base de datos.** Nadie lee ni escribe la base de otro servicio.
2. **Para conocer algo de otro servicio se usan identificadores o eventos**, nunca llamadas directas entre funciones Lambda.
3. **El tenant siempre sale del token** (ya verificado), nunca de lo que escriba el usuario en la petición.
4. **Todo dato guardado lleva su `tenant_id`.**

## 5. Seguridad: autenticación y autorización

- **Autenticación (quién eres):** el usuario envía correo y contraseña al servicio 1. Si son correctos, recibe un **token JWT** que contiene `usuario_id`, `tenant_id` y `rol`, con tiempo de expiración.
- **Validación:** API Gateway (HTTP API) detiene cada petición protegida y ejecuta el **Lambda Authorizer**, que revisa que el token sea auténtico y no esté vencido. Si no lo es, la petición se rechaza y el servicio **nunca se ejecuta**. Si lo es, el servicio recibe la petición con `tenant_id`, `usuario_id` y `rol`.
- **Autorización (qué puedes hacer):** cada servicio revisa el `rol` según la tabla de permisos.
- **Rutas públicas** (sin token): solo `POST /usuarios/login` y el registro de una nueva empresa. **Todo lo demás es protegido.**
- **Clave secreta del token:** variable de entorno `JWT_SECRET` (nunca en el código ni en el repositorio). Todos los servicios y el authorizer usan la misma.
- **Hash de contraseña:** por ahora SHA-256. **\[VERIFICAR\]** si el curso exige un algoritmo más fuerte (bcrypt o similar).
- **Códigos 401 vs 403 del token:** el Flujo 8 pide 401 si falta el token y 403 si está vencido o alterado. Con HTTP API y respuestas simples del authorizer, API Gateway puede devolver el mismo rechazo en ambos casos. **\[VERIFICAR\]** en una prueba real y ajustar si hace falta.

### Permisos por rol

| Acción | vendedor | gerente | admin |
| --- | :-: | :-: | :-: |
| Ver clientes, oportunidades, actividades, cotizaciones del tenant | ✔ | ✔ | ✔ |
| Crear y editar clientes, contactos, oportunidades, actividades, cotizaciones | ✔ | ✔ | ✔ |
| Eliminar clientes, oportunidades, cotizaciones | ✘ | ✔ | ✔ |
| Reasignar responsable de un cliente u oportunidad | ✘ | ✔ | ✔ |
| Gestionar productos (crear, editar, desactivar) | ✘ | ✔ | ✔ |
| Crear y desactivar usuarios | ✘ | ✘ | ✔ |

**\[CONFIRMAR\]** esta matriz.

## 6. Reglas de nombres (obligatorias para todos)

Se siguen las convenciones usadas en clase (`t_usuarios`, `t_productos`, `CrearUsuario`).

| Qué | Regla | Ejemplo |
| --- | --- | --- |
| **Idioma** | Todo en **español**, sin mezclar inglés (salvo palabras técnicas como `token`, `tenant`, `api`) | `t_clientes`, `fecha_creacion` |
| **Tablas** | Prefijo `t_`, minúsculas, plural, `snake_case` | `t_oportunidades` |
| **Campos** | Minúsculas, `snake_case`, sin tildes ni eñes | `fecha_cierre_estimada`, `anio` |
| **Identificadores** | Siempre texto, con prefijo del tipo | `cli_000123`, `opo_000045` |
| **Funciones Lambda** | `PascalCase`, verbo + entidad | `CrearCliente`, `ListarOportunidades` |
| **Rutas** | Minúsculas, sustantivo en plural | `/clientes`, `/clientes/{cliente_id}` |
| **Eventos** | `entidad.accion` en minúsculas, acción en pasado | `oportunidad.ganada` |
| **Valores fijos** (etapas, estados, roles) | Minúsculas, sin tildes, `snake_case` | `en_negociacion`, `vendedor` |
| **Fechas** | Texto en formato ISO 8601 en UTC | `2026-11-10T15:30:00Z` |
| **Dinero** | Campo numérico + campo `moneda` | `monto_estimado: 80000`, `moneda: "PEN"` |
| **Respuestas de error** | Siempre con `codigo` y `mensaje` | `{"codigo": "no_autorizado", "mensaje": "..."}` |

### Prefijos de identificadores

| Entidad | Prefijo | Ejemplo |
| --- | --- | --- |
| Tenant | `ten_` | `ten_seguros` |
| Usuario | `usr_` | `usr_000012` |
| Cliente | `cli_` | `cli_000123` |
| Contacto | `con_` | `con_000456` |
| Oportunidad | `opo_` | `opo_000045` |
| Actividad | `act_` | `act_000789` |
| Producto | `pro_` | `pro_000010` |
| Cotización | `cot_` | `cot_000321` |
| Notificación | `not_` | `not_000654` |
| Evento | `evt_` | `evt_000987` |

En los datos ficticios los números son secuenciales para que los servicios sean coherentes entre sí (una oportunidad debe apuntar a un `cliente_id` que **sí exista**). Al crear datos desde la aplicación, el identificador puede generarse de otra forma, pero **siempre con su prefijo y siempre como texto**.

### Campos comunes en todas las tablas

`tenant_id`, `fecha_creacion` y `fecha_actualizacion` aparecen en todas las tablas principales. El `tenant_id` es la base del aislamiento: toda consulta se hace **dentro** de un tenant.

## 7. Los microservicios en detalle

Para cada servicio: qué hace, qué no hace, qué guarda, qué rutas ofrece y qué eventos publica o escucha. La base es **DynamoDB** (NoSQL) en todos los servicios. El enunciado permite elegir SQL o NoSQL según convenga a cada servicio, y elegimos DynamoDB porque es nativo de serverless, no hay un servidor de base de datos que administrar y el aislamiento por tenant se resuelve con el tenant\_id en la clave. Si algún servicio necesitara SQL, el enunciado exige un único RDS con el patrón Single Database, Multiple Schemas y presentar su diagrama entidad-relación. Con DynamoDB, cada tabla se presenta como estructura JSON en el informe; aquí se describe como lista de campos.

### 7.1 Usuarios y Tenants

**Qué hace:** registra empresas y usuarios, hace el login, entrega el token y administra los roles.

**Qué NO hace:** no guarda datos de clientes, ventas ni tareas. No valida tokens de las demás peticiones (eso lo hace el Authorizer).

**Tabla `t_tenants`**

| Campo | Descripción |
| --- | --- |
| `tenant_id` | Identificador de la empresa |
| `nombre` | Nombre comercial |
| `nombre_normalizado` | Nombre en minúsculas y sin espacios de más. Sirve para detectar empresas duplicadas (GSI `nombre_normalizado-index`) |
| `rubro` | Sector de la empresa |
| `estado` | `activo`, `suspendido` |
| `fecha_creacion` | Fecha de alta |

**Tabla `t_tenants_locks`**

Candado para que dos registros simultáneos no creen la misma empresa. No es una tabla de negocio; solo guarda el nombre ya tomado.

| Campo | Descripción |
| --- | --- |
| `nombre_normalizado` | Clave única. Si ya existe, el registro se rechaza |
| `fecha_creacion` | Cuándo se tomó el candado |

Al registrar un tenant se escribe primero el candado (con condición de que no exista). Si después falla el alta del tenant, se borra el candado.

**Tabla `t_usuarios`**

| Campo | Descripción |
| --- | --- |
| `tenant_id` | A qué empresa pertenece |
| `usuario_id` | Identificador del usuario |
| `nombre` | Nombre completo |
| `correo` | Correo de acceso. **\[CONFIRMAR\]** único en todo el sistema, para que el login solo pida correo y contraseña |
| `contrasena_hash` | Contraseña cifrada (nunca en texto plano) |
| `rol` | `admin`, `gerente`, `vendedor` |
| `estado` | `activo`, `inactivo` |
| `fecha_creacion` | Fecha de alta |

**Rutas principales**

| Ruta | Para qué | Protegida |
| --- | --- | :-: |
| `POST /usuarios/login` | Entrega el token | No |
| `POST /tenants` | Registrar una empresa con su primer admin | No |
| `POST /usuarios` | Crear usuario en el tenant | Sí (admin) |
| `GET /usuarios` | Listar usuarios del tenant | Sí |
| `PUT /usuarios/{usuario_id}` | Editar rol o estado | Sí (admin) |

**Eventos:** publica `usuario.creado`. No escucha ninguno.

**\[VERIFICAR\]** Usuarios ya publica en el topic SNS compartido, pero todavía no hay colas SQS ni servicio de Notificaciones que consuma. Cuando exista el consumidor, confirmar que el mensaje llega y que el atributo `tipo` permite filtrar.

### 7.2 Clientes

**Qué hace:** guarda las cuentas del tenant y sus contactos.

**Qué NO hace:** no guarda oportunidades ni tareas. Solo sabe de clientes y contactos.

**Tabla `t_clientes`**

| Campo | Descripción |
| --- | --- |
| `tenant_id`, `cliente_id` | Identificación |
| `nombre` | Razón social o nombre de la persona |
| `tipo` | `empresa`, `persona` |
| `documento` | RUC o DNI |
| `correo`, `telefono` | Datos de contacto |
| `industria` | Sector del cliente |
| `ciudad` | Ciudad |
| `estado` | `prospecto`, `activo`, `inactivo` |
| `responsable_id` | `usuario_id` del vendedor a cargo |
| `fecha_creacion`, `fecha_actualizacion` | Fechas |

**Tabla `t_contactos`**

| Campo | Descripción |
| --- | --- |
| `tenant_id`, `contacto_id` | Identificación |
| `cliente_id` | A qué cliente pertenece |
| `nombre`, `cargo`, `correo`, `telefono` | Datos de la persona |
| `es_principal` | Si es el contacto principal del cliente (verdadero/falso) |
| `fecha_creacion` | Fecha de alta |

**Rutas principales:** `POST /clientes`, `GET /clientes`, `GET /clientes/{cliente_id}`, `PUT /clientes/{cliente_id}`, `DELETE /clientes/{cliente_id}`, `POST /clientes/{cliente_id}/contactos`, `GET /clientes/{cliente_id}/contactos`. Todas protegidas (HTTP API + Lambda Authorizer). Un vendedor no puede eliminar ni reasignar `responsable_id`. Si el `responsable_id` no se envía al crear, se usa el `usuario_id` del token.

**Eventos:** publica `cliente.creado`. No escucha ninguno. **\[VERIFICAR\]** igual que Usuarios: el evento se publica; el consumo queda para Notificaciones.

### 7.3 Oportunidades

**Qué hace:** gestiona el pipeline de ventas. Registra cada oportunidad, su monto, su etapa y el historial de cambios de etapa. Es el servicio central del CRM.

**Qué NO hace:** no guarda datos del cliente (solo su `cliente_id`), ni cotizaciones, ni tareas.

**Etapas del pipeline** (valores fijos, en este orden):

`nueva` → `calificada` → `propuesta` → `en_negociacion` → `ganada` o `perdida`

**Reglas:** una oportunidad `ganada` o `perdida` queda cerrada y no se reabre. Al marcar `perdida` es obligatorio indicar `motivo_perdida`.

**Tabla `t_oportunidades`**

| Campo | Descripción |
| --- | --- |
| `tenant_id`, `oportunidad_id` | Identificación |
| `cliente_id` | Cliente al que se le intenta vender |
| `titulo` | Descripción corta |
| `monto_estimado`, `moneda` | Valor estimado de la venta |
| `etapa` | Una de las etapas del pipeline |
| `probabilidad` | Número de 0 a 100 |
| `fecha_cierre_estimada` | Cuándo se espera cerrar |
| `responsable_id` | `usuario_id` del vendedor a cargo |
| `motivo_perdida` | Solo si está `perdida` |
| `fecha_creacion`, `fecha_actualizacion` | Fechas |

**Tabla `t_historial_etapas`**

| Campo | Descripción |
| --- | --- |
| `tenant_id`, `historial_id` | Identificación |
| `oportunidad_id` | A qué oportunidad pertenece |
| `etapa_anterior`, `etapa_nueva` | Cambio realizado |
| `usuario_id` | Quién lo hizo |
| `fecha_cambio` | Cuándo |

**Rutas principales:** `POST /oportunidades`, `GET /oportunidades`, `GET /oportunidades/{oportunidad_id}`, `PUT /oportunidades/{oportunidad_id}`, `PUT /oportunidades/{oportunidad_id}/etapa`, `GET /oportunidades/{oportunidad_id}/historial`.

**Eventos:** publica `oportunidad.creada`, `oportunidad.etapa_cambiada`, `oportunidad.ganada`, `oportunidad.perdida`. Escucha `cotizacion.aceptada`.

### 7.4 Actividades

**Qué hace:** gestiona el seguimiento comercial: llamadas, reuniones, correos y tareas, con fecha y responsable. Algunas se crean a mano y otras automáticamente por eventos.

**Qué NO hace:** no cambia etapas de oportunidades ni envía avisos.

**Tabla `t_actividades`**

| Campo | Descripción |
| --- | --- |
| `tenant_id`, `actividad_id` | Identificación |
| `tipo` | `llamada`, `reunion`, `correo`, `tarea` |
| `titulo`, `descripcion` | Qué hay que hacer |
| `cliente_id` | Cliente relacionado |
| `oportunidad_id` | Oportunidad relacionada (puede estar vacío) |
| `responsable_id` | Quién debe hacerla |
| `fecha_programada` | Cuándo |
| `estado` | `pendiente`, `completada`, `cancelada` |
| `origen` | `manual`, `automatica` |
| `fecha_creacion`, `fecha_actualizacion` | Fechas |

**Rutas principales:** `POST /actividades`, `GET /actividades`, `GET /actividades/{actividad_id}`, `PUT /actividades/{actividad_id}`, `PUT /actividades/{actividad_id}/completar`.

**Eventos:** publica `actividad.completada`. Escucha `oportunidad.etapa_cambiada`, `oportunidad.ganada`, `oportunidad.perdida`, `cotizacion.enviada`.

### 7.5 Productos y Cotizaciones

**Qué hace:** mantiene el catálogo de lo que vende el tenant y permite armar cotizaciones para una oportunidad.

**Qué NO hace:** no cambia el estado de la oportunidad directamente; solo avisa con eventos.

**Tabla `t_productos`**

| Campo | Descripción |
| --- | --- |
| `tenant_id`, `producto_id` | Identificación |
| `nombre`, `descripcion`, `categoria` | Datos del producto |
| `precio`, `moneda` | Precio de lista |
| `estado` | `activo`, `inactivo` |
| `fecha_creacion`, `fecha_actualizacion` | Fechas |

**Tabla `t_cotizaciones`**

| Campo | Descripción |
| --- | --- |
| `tenant_id`, `cotizacion_id` | Identificación |
| `oportunidad_id`, `cliente_id` | A qué venta y cliente corresponde |
| `estado` | `borrador`, `enviada`, `aceptada`, `rechazada` |
| `items` | Lista incrustada en la misma cotización; cada ítem lleva `producto_id`, `nombre_producto`, `cantidad`, `precio_unitario`, `subtotal` |
| `total`, `moneda` | Monto total |
| `fecha_vencimiento` | Hasta cuándo es válida |
| `creada_por` | `usuario_id` |
| `fecha_creacion`, `fecha_actualizacion` | Fechas |

Los ítems guardan una copia del nombre y el precio al momento de cotizar, para que un cambio posterior en el catálogo no altere cotizaciones ya emitidas.

**Rutas principales:** `POST /productos`, `GET /productos`, `PUT /productos/{producto_id}`, `POST /cotizaciones`, `GET /cotizaciones`, `GET /cotizaciones/{cotizacion_id}`, `PUT /cotizaciones/{cotizacion_id}/enviar`, `PUT /cotizaciones/{cotizacion_id}/aceptar`, `PUT /cotizaciones/{cotizacion_id}/rechazar`.

**Eventos:** publica `cotizacion.enviada`, `cotizacion.aceptada`, `cotizacion.rechazada`. No escucha ninguno.

### 7.6 Notificaciones

**Qué hace:** escucha eventos de los demás servicios y registra avisos para los usuarios. Los usuarios consultan sus avisos y los marcan como leídos.

**Qué NO hace:** no decide ni cambia nada en el negocio. Solo reacciona.

**Tabla `t_notificaciones`**

| Campo | Descripción |
| --- | --- |
| `tenant_id`, `notificacion_id` | Identificación |
| `usuario_destino_id` | A quién va dirigida (puede estar vacío) |
| `rol_destino` | A qué rol va dirigida, por ejemplo `gerente` (puede estar vacío) |
| `tipo` | Tipo de aviso, igual al nombre del evento que lo originó |
| `titulo`, `mensaje` | Texto del aviso |
| `evento_id` | Evento que la originó |
| `leida` | Verdadero/falso |
| `fecha_creacion` | Cuándo se generó |

**Decisión de diseño:** como Notificaciones no puede consultar la base de Usuarios, un aviso se dirige a un usuario concreto (cuando el evento trae su `usuario_id`, como `responsable_id`) **o a un rol** (por ejemplo, todos los gerentes del tenant). Al consultar, cada usuario ve los avisos dirigidos a él o a su rol.

**Rutas principales:** `GET /notificaciones`, `PUT /notificaciones/{notificacion_id}/leer`.

**Eventos:** no publica ninguno. Escucha todos los del catálogo (sección 8).

## 8. Eventos: cómo se hablan los servicios

Un servicio **publica** un anuncio en **SNS** (el altavoz). Cada servicio interesado tiene su **cola SQS** (el buzón) y recibe una copia. Quien publica no sabe quién escucha.

### Formato común de todo evento

| Campo | Descripción |
| --- | --- |
| `evento_id` | Identificador único del evento |
| `tipo` | Nombre del evento, por ejemplo `oportunidad.ganada` |
| `tenant_id` | A qué empresa pertenece (**siempre presente**) |
| `fecha` | Cuándo ocurrió |
| `datos` | Información propia de cada evento (ver tabla) |

### Catálogo de eventos

| Evento | Lo publica | Lo escuchan | Qué hacen | `datos` que lleva |
| --- | --- | --- | --- | --- |
| `usuario.creado` | Usuarios | Notificaciones | Aviso de bienvenida | `usuario_id`, `nombre`, `rol` |
| `cliente.creado` | Clientes | Notificaciones | Avisa al responsable | `cliente_id`, `nombre`, `responsable_id` |
| `oportunidad.creada` | Oportunidades | Notificaciones | Avisa al responsable | `oportunidad_id`, `cliente_id`, `titulo`, `monto_estimado`, `responsable_id` |
| `oportunidad.etapa_cambiada` | Oportunidades | Actividades, Notificaciones | Actividades crea un seguimiento automático; Notificaciones avisa | `oportunidad_id`, `cliente_id`, `etapa_anterior`, `etapa_nueva`, `responsable_id` |
| `oportunidad.ganada` | Oportunidades | Actividades, Notificaciones | Actividades crea tarea de entrega/inicio; Notificaciones avisa al gerente y al responsable | `oportunidad_id`, `cliente_id`, `titulo`, `monto_estimado`, `responsable_id` |
| `oportunidad.perdida` | Oportunidades | Actividades, Notificaciones | Actividades cancela tareas pendientes de esa oportunidad; Notificaciones avisa | `oportunidad_id`, `cliente_id`, `motivo_perdida`, `responsable_id` |
| `cotizacion.enviada` | Cotizaciones | Actividades, Notificaciones | Actividades crea seguimiento a unos días; Notificaciones avisa | `cotizacion_id`, `oportunidad_id`, `cliente_id`, `total`, `creada_por` |
| `cotizacion.aceptada` | Cotizaciones | Oportunidades, Notificaciones | Oportunidades la marca como `ganada` (y publica `oportunidad.ganada`); Notificaciones avisa | `cotizacion_id`, `oportunidad_id`, `cliente_id`, `total` |
| `cotizacion.rechazada` | Cotizaciones | Notificaciones | Avisa al responsable | `cotizacion_id`, `oportunidad_id`, `cliente_id`, `creada_por` |
| `actividad.completada` | Actividades | Notificaciones | Avisa al responsable de la oportunidad (opcional) | `actividad_id`, `oportunidad_id`, `responsable_id` |

**Opcional si sobra tiempo:** aviso de tarea por vencer. Requiere una revisión programada, así que queda fuera de la versión base.

### Quién escucha a quién (resumen)

- **Notificaciones** escucha todo.
- **Actividades** escucha cambios de oportunidades y envíos de cotizaciones.
- **Oportunidades** escucha solo `cotizacion.aceptada`.
- **Usuarios** y **Clientes** no escuchan nada.

Cuidado con los ciclos: Oportunidades escucha una cotización aceptada y publica `oportunidad.ganada`; esa cadena es intencional y **termina ahí**. Nadie debe publicar un evento como reacción a un evento que lo originó a él mismo.

## 9. Flujos de uso

Estos flujos son la base de la demo y de las pruebas. Cada integrante debe poder explicar el flujo donde participa su servicio.

### Flujo 1: Una empresa nueva se registra

1. Se registra el tenant (Seguros Andinos) con su primer usuario admin (`POST /tenants`).
2. El admin hace login y recibe su token.
3. El admin crea usuarios para su equipo (vendedores y un gerente).
4. Se publica `usuario.creado` y cada usuario nuevo recibe un aviso de bienvenida.

### Flujo 2: Entrar al sistema

1. El usuario envía correo y contraseña a `POST /usuarios/login`.
2. Si son correctos, recibe un token con su `usuario_id`, `tenant_id` y `rol`, y fecha de expiración.
3. En cada petición posterior envía el token. El Authorizer lo valida antes de dejar pasar.
4. Si el token vence, el usuario vuelve a iniciar sesión.

### Flujo 3: Registrar un cliente y sus contactos

1. El vendedor crea el cliente Constructora Andes y se queda como `responsable_id`.
2. Agrega a Ana (gerente de compras) como contacto principal.
3. Se publica `cliente.creado` y el responsable recibe un aviso.

### Flujo 4: Una venta exitosa de principio a fin

1. El vendedor crea la oportunidad "Seguro de flota" en etapa `nueva` (`oportunidad.creada`).
2. Avanza la oportunidad por `calificada`, `propuesta` y `en_negociacion`. En cada cambio se publica `oportunidad.etapa_cambiada`, Actividades crea un seguimiento automático y el historial guarda el cambio.
3. Un integrante de ventas arma una cotización con los productos del catálogo y la envía (`cotizacion.enviada`). Actividades programa un seguimiento y se notifica al equipo.
4. El cliente acepta. Se marca la cotización como aceptada (`cotizacion.aceptada`).
5. Oportunidades escucha el evento, marca la oportunidad como `ganada` y publica `oportunidad.ganada`.
6. Actividades crea la tarea de inicio de servicio y Notificaciones avisa al gerente y al vendedor.

### Flujo 5: La cotización es rechazada

1. El cliente rechaza la cotización (`cotizacion.rechazada`).
2. El responsable recibe un aviso.
3. La oportunidad **no se pierde automáticamente**: el vendedor decide si prepara una nueva cotización o marca la oportunidad como perdida.

### Flujo 6: Una oportunidad se pierde

1. El vendedor marca la oportunidad como `perdida` indicando el `motivo_perdida`.
2. Se publica `oportunidad.perdida`.
3. Actividades cancela las tareas pendientes de esa oportunidad y Notificaciones avisa al gerente.

### Flujo 7: Seguimiento diario de un vendedor

1. El vendedor consulta sus actividades pendientes.
2. Realiza una llamada y la marca como completada (`actividad.completada`).
3. Crea manualmente una nueva actividad de seguimiento.
4. Revisa sus notificaciones y las marca como leídas.

### Flujo 8: Acceso denegado

Casos que deben comportarse así y que se prueban en la demo:

- **Token ausente, vencido o alterado:** si no se envía token (cabecera Authorization ausente) la respuesta es 401; si el token está vencido o alterado la respuesta es 403. En ambos casos la petición se rechaza y el servicio nunca se ejecuta.
- **Rol insuficiente:** un vendedor intenta eliminar un cliente. Se rechaza (403).
- **Dato de otro tenant:** un usuario de ElectroHogar pide un cliente de Seguros Andinos. La respuesta es "no existe" (404), porque el servicio solo busca dentro del tenant del token.

### Flujo 9: Demo con 2 tenants

1. Login como admin de `ten_seguros` y como admin de `ten_electro`.
2. Mostrar que cada uno ve únicamente sus clientes, oportunidades y avisos.
3. Ejecutar el Flujo 4 en un tenant y mostrar que el otro no se entera.
4. Ejecutar el Flujo 8 para demostrar el aislamiento y la protección.

## 10. Datos ficticios

- Mínimo **30,000 registros por microservicio**, repartidos en los 3 tenants (unos 10,000 por tenant). **\[CONFIRMAR\]** tabla principal de cada servicio con 30,000 o más: `t_usuarios`, `t_clientes`, `t_oportunidades`, `t_actividades`, `t_cotizaciones` (con `t_productos` en su misma base) y `t_notificaciones`.
- **Los datos deben ser coherentes entre servicios:** toda oportunidad apunta a un `cliente_id` que existe en el mismo tenant; toda cotización a una oportunidad existente; todo `responsable_id` a un usuario existente.
- Por eso el orden de generación es: usuarios y tenants, luego clientes, luego oportunidades, luego actividades y cotizaciones, luego notificaciones. **Una sola persona** genera todos los datos con un mismo programa para garantizar coherencia.
- La cantidad de usuarios por tenant (10,000) es poco realista, pero cumple el mínimo. **\[CONFIRMAR\]** con el profesor si se acepta o si prefieren otra distribución.

## 11. Cómo trabajamos como grupo

### Repositorio y código

- **Un solo repositorio público** de GitHub con una carpeta por servicio (`usuarios`, `clientes`, `oportunidades`, `actividades`, `productos_cotizaciones`, `notificaciones`), una carpeta para el authorizer y las piezas compartidas, y otra para el frontend.
- Cada avance se sube con frecuencia, aunque esté a medias. **Si no está en el repositorio, para el grupo no existe.**
- Nada de claves ni credenciales en el repositorio.

### Despliegue

- Cada integrante tiene su propia cuenta de AWS, así que **cada quien despliega su propia copia** con el mismo código y la misma configuración de Serverless Framework.
- Cada servicio tiene su propio archivo de configuración de Serverless Framework.
- Nombres de recursos y etapas de despliegue idénticos para todos (a definir en un documento técnico aparte).
- **Prueba temprana obligatoria:** antes de programar nada serio, todos despliegan un ejemplo mínimo para confirmar que pueden hacerlo en sus cuentas de AWS Academy.
- Para la demo, un solo integrante despliega todo en su cuenta.

### Trabajo en paralelo

Una vez aprobado este documento, se puede avanzar a la vez en:

1. Cada microservicio (a partir de su sección en este documento).
2. El FrontEnd, usando datos de prueba según las rutas y campos de este documento.
3. El diagrama de arquitectura.
4. La generación de datos ficticios.
5. El informe y la presentación, desde las secciones de este documento.

### Hitos

| Fecha | Qué |
| --- | --- |
| *(por definir)* | Documento base aprobado por todos |
| *(por definir)* | Despliegue de prueba exitoso por cada integrante |
| Sábado 14-nov-2026 | Exposición virtual con ACL, con avance proporcional al 30% |
| Domingo 22-nov-2026, 23:59 | Entrega en Canvas: informe, PowerPoint y enlaces a repositorios |
| Semana 16 | Exposición presencial y demo |

## 12. Cambios a este documento

Cualquier cambio de nombres, campos, rutas o eventos se hace **primero aquí** y se avisa al grupo. Quien necesite algo de otro servicio lo pide a su responsable y se registra en esta sección.

| Fecha | Qué cambió | Quién |
| --- | --- | --- |
| 2026-11-04 | Candado `t_tenants_locks` y campo `nombre_normalizado` para no duplicar empresas. Advertencias a verificar: 401 vs 403 del authorizer, hash SHA-256, eventos SNS sin consumidores todavía. | Castro |

## 13. Decisiones pendientes

- [x] Aprobar la matriz de permisos por rol (sección 5).
- [x] Confirmar que el correo es único en todo el sistema (sección 7.1).
- [x] Confirmar dónde se guarda la clave secreta del token en AWS Academy.
- [x] Confirmar qué 2 tenants se usan en la demo (sección 3).
- [x] Confirmar la distribución de los 30,000 registros por servicio (sección 10).
- [x] Confirmar que todos los servicios usan DynamoDB (el enunciado permite SQL o NoSQL por servicio).

## 14. Para verificar más adelante

- [ ] **401 vs 403:** petición sin cabecera `Authorization` → 401; token vencido o alterado → 403. Probar contra HTTP API + authorizer de respuestas simples y ajustar si API Gateway unifica ambos rechazos.
- [ ] **Hash de contraseña:** SHA-256 es lo que usa Usuarios hoy. Cambiar a bcrypt (u otro) si el enunciado o el profesor lo piden.
- [ ] **Consumo de eventos:** Usuarios y Clientes publican en el topic SNS compartido (`usuario.creado`, `cliente.creado`). Cuando existan las colas SQS de Notificaciones (y las demás), comprobar suscripción, filtro por atributo `tipo` y el formato del mensaje.
