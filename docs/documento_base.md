# Documento Base – CRM SaaS

*CS2032 Cloud Computing · Proyecto Final · Ciclo 2026-2*

> **Guía vigente del repositorio · actualización: 2026-11-11.** Este documento reúne el contrato funcional, el estado de implementación y la evidencia de validación. Una funcionalidad descrita no implica que esté implementada o probada en AWS. Los cambios de contrato se registran aquí junto con su implementación; los acuerdos pendientes se señalan como **[DECIDIR]**.

## 0. Estado actual y cómo usar esta guía

### Tres estados que se registran por separado

- **Diseñado:** existe un contrato de datos, rutas o eventos en este documento. Puede tener decisiones pendientes.
- **Implementado:** existe código y configuración en el repositorio. Su validación local se indica por separado.
- **Verificado en AWS:** hay evidencia de ejecución del caso con fecha, cuenta o entorno, stage y resultado. Un archivo de Serverless o una colección Postman no constituyen esa evidencia.

La revisión del 2026-11-11 y sus pruebas son locales. **No se ha acreditado aquí ningún despliegue ni flujo completo en AWS.** Si el grupo ya realizó pruebas, debe incorporar sus evidencias en la sección 14.

### Inventario del repositorio

| Componente | Diseñado | Implementado en código | Validación local | Verificado en AWS |
| --- | --- | --- | --- | --- |
| Compartido: JWT, Authorizer, SNS, capas | Sí | Sí; Authorizer comprueba identidad vigente | Pruebas de JWT, estado, rol e infraestructura | Pendiente de evidencia |
| Usuarios y Tenants | Sí | Registro atómico, login, gestión de usuarios, candados de correo y outbox | Pruebas de registro, conflictos, migración de hash y protección de admins | Pendiente de evidencia |
| Clientes y contactos | Sí | CRUD con borrado lógico; contacto principal atómico; filtro por responsable; outbox | Pruebas de permisos, validaciones, archivo y conflictos | Pendiente de evidencia |
| Oportunidades | Sí | Pipeline, historial, borrado lógico, outbox y consumidor SQS | Importaciones, transacción de cierre y reintentos del consumidor | Pendiente de evidencia |
| Notificaciones | Sí | Consumidor SQS con DLQ, deduplicación por evento y destino, lectura individual por usuario, `GET /notificaciones` y `PUT /notificaciones/{notificacion_id}/leer` | Pruebas locales con boto3 simulado: sobre SNS, duplicados, aislamiento por tenant, lectura por rol, paginación y errores | Pendiente de evidencia | 
| Productos y Cotizaciones | Contrato inicial | No | No aplica | Pendiente |
| Actividades | Contrato inicial | No | No aplica | Pendiente |
| Generación/carga de datos ficticios | Requisitos definidos | `generar_datos.py` y `cargar_datos.py` vacíos; sí existe migración de integridad | Migración cubierta por pruebas locales | Pendiente |
| Frontend Amplify | Visión funcional | No hay código en este repositorio | No aplica | Pendiente |
| Pruebas y herramientas | Colección Postman y validación local | Suite local ejecutada y omitida del remoto por ser material de trabajo | Ver [validación local](validacion_local.md) | Postman pendiente de ejecución documentada |

### Correcciones realizadas el 2026-11-11

| Problema anterior | Corrección implementada | Evidencia o límite |
| --- | --- | --- |
| `src.utilidades` no coincidía con `Utilidades.py` | Archivo renombrado a `utilidades.py` | Todos los handlers se importan en la suite local |
| SHA-256 sin sal | PBKDF2-HMAC-SHA256, 600,000 iteraciones y sal aleatoria por contraseña | Nuevos registros seguros; hashes SHA-256 existentes migran al iniciar sesión correctamente |
| Un JWT seguía habilitado tras desactivación o cambio de rol | Authorizer lee usuario y tenant con consistencia fuerte en cada petición; TTL de caché 0; JWT nuevo dura 1 hora | Usuario inactivo, rol distinto o tenant suspendido rechazan acceso; petición ya autorizada puede terminar |
| Tenant y admin podían quedar parcialmente registrados | Una transacción guarda tenant, candado de nombre, usuario, candado de correo y evento pendiente | Fallos condicionales de correo/nombre devuelven 409; falta prueba real de concurrencia en AWS |
| Correos duplicados por peticiones simultáneas | `t_correos_locks` global; usado por CrearTenant y CrearUsuario en la misma transacción | Datos existentes necesitan `datos/migrar_integridad.py` con escrituras pausadas |
| Un admin podía desactivarse o quitarse su rol | 409 `autoproteccion_admin`; cambios a otros usuarios comprueban que el solicitante sigue siendo admin activo dentro de la transacción | Evita también dos admins desactivándose mutuamente; 404 si el usuario objetivo desaparece |
| JSON incorrecto provocaba fallos no controlados | Capa `crm_comun`: body objeto JSON, manejo de base64, claims, respuestas y errores de negocio | Usuarios, Clientes y Oportunidades usan la misma capa |
| ActualizarCliente no capturaba fallo condicional | Traduce carrera con borrado a 404; condición comprueba que el registro no está archivado | Prueba local del fallo condicional |
| Más de un contacto principal | `contacto_principal_id` en cliente reservado junto con el contacto en una transacción | Segundo principal devuelve 409; `es_principal` exige booleano; migrar datos existentes |
| Responsable inválido | Se exige `usr_` seguido de caracteres alfanuméricos; se conserva la restricción del vendedor | No acredita que ese usuario exista: no se consulta la base de otro servicio |
| Borrado físico dejaba referencias huérfanas | Clientes y Oportunidades se archivan con `eliminado` y `fecha_eliminacion`; contactos e historial se conservan | GET/edición/listado habitual excluyen archivados; no hay borrado en cascada ni evento de eliminación |
| Cambios guardados sin evento si fallaba SNS | Outbox por servicio: dato + evento en transacción; publicador programado cada minuto reintenta los pendientes | Entrega al menos una vez; consumidores deben deduplicar; no garantiza orden global |
| Configuración ligada a un integrante | Se quitaron `org`/`app` del stack compartido; todos usan Framework 4 y capa común | AWS Academy/LabRole y programación del publicador requieren verificación real |
| Listado “mis clientes” sin índice | GSI `responsable_id-index` y filtro `GET /clientes?responsable_id=usr_...` | El GSI y su construcción sobre datos existentes requieren despliegue |
| `cliente_nombre` podía quedar desactualizado | Se conserva como instantánea opcional, y se documenta como limitación aceptada de esta versión | No se implementa sincronización ni evento `cliente.actualizado` |

### Próximos pasos

1. Desplegar y migrar estas correcciones en un entorno de prueba; completar la matriz de la sección 14.
2. Implementar **Notificaciones**, definiendo primero deduplicación por evento/destino y lectura individual de avisos por rol.
3. Implementar **Productos y Cotizaciones**, para conectar `cotizacion.aceptada` con Oportunidades.
4. Implementar **Actividades**, y avanzar en paralelo con frontend, datos coherentes, informe y demo.

### Regla de mantenimiento

Cada contribución que cambie comportamiento actualiza: contrato de la sección 7 u 8, inventario anterior, historial de la sección 12, pruebas locales y evidencia AWS cuando exista. Registrar responsable y fecha de la evidencia. No marcar **verificado en AWS** basándose únicamente en revisión de código o mocks.

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

**Decisión:** demo con `ten_seguros` y `ten_electro`.

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
2. **Para conocer algo de otro servicio se usan identificadores o eventos**, nunca llamadas directas entre funciones Lambda. El Authorizer pertenece a la infraestructura de identidad y puede consultar las tablas de Usuarios y Tenants para comprobar el acceso vigente; ningún microservicio de negocio consulta tablas ajenas.
3. **El tenant siempre sale del token** (ya verificado), nunca de lo que escriba el usuario en la petición.
4. **Todo dato guardado lleva su `tenant_id`.**

## 5. Seguridad: autenticación y autorización

- **Autenticación (quién eres):** el usuario envía correo y contraseña al servicio 1. Si son correctos, recibe un **token JWT** que contiene `usuario_id`, `tenant_id` y `rol`, con tiempo de expiración.
- **Validación:** API Gateway (HTTP API) detiene cada petición protegida y ejecuta el **Lambda Authorizer**, que revisa firma y expiración y lee el usuario y tenant actuales con consistencia fuerte. Exige ambos activos y que el rol del token coincida con el rol vigente. La caché está deshabilitada. Si no lo es, la petición se rechaza y el servicio **nunca se ejecuta**. Si lo es, el servicio recibe la petición con `tenant_id`, `usuario_id` y `rol`.
- **Autorización (qué puedes hacer):** cada servicio revisa el `rol` según la tabla de permisos.
- **Rutas públicas** (sin token): solo `POST /usuarios/login` y el registro de una nueva empresa. **Todo lo demás es protegido.**
- **Clave secreta del token:** variable de entorno `JWT_SECRET` (nunca en código ni repositorio), utilizada por Usuarios para emitir tokens y por el Authorizer para verificarlos. Los demás servicios reciben las claims verificadas; no necesitan la clave.
- **Contraseñas:** PBKDF2-HMAC-SHA256 con 600,000 iteraciones y sal aleatoria de 16 bytes. Se guarda `pbkdf2_sha256$iteraciones$sal$hash` en `contrasena_hash`. Los SHA-256 previos solo se admiten para verificar y migrar tras un login correcto. No se devuelve el hash en respuestas. Los JWT nuevos expiran en 1 hora; tokens anteriores conservan su expiración pero pasan la comprobación del estado y rol actuales.
- **Códigos 401 vs 403 del token:** el Flujo 8 pide 401 si falta el token y 403 si está vencido o alterado. Con HTTP API y respuestas simples del authorizer, API Gateway puede devolver el mismo rechazo en ambos casos. **\[VERIFICAR\]** en una prueba real y ajustar si hace falta.

### Permisos por rol

| Acción | vendedor | gerente | admin |
| --- | :-: | :-: | :-: |
| Ver clientes, oportunidades, actividades, cotizaciones del tenant | ✔ | ✔ | ✔ |
| Crear y editar clientes, contactos, oportunidades, actividades, cotizaciones | ✔ | ✔ | ✔ |
| Cambiar la etapa de una oportunidad | ✔ | ✔ | ✔ |
| Eliminar clientes, oportunidades, cotizaciones | ✘ | ✔ | ✔ |
| Reasignar responsable de un cliente u oportunidad | ✘ | ✔ | ✔ |
| Gestionar productos (crear, editar, desactivar) | ✘ | ✔ | ✔ |
| Crear y desactivar usuarios | ✘ | ✘ | ✔ |

**Decisión:** matriz aprobada según sección 13. *(Se agregó la fila "Cambiar la etapa de una oportunidad" para dejar explícito lo que ya implicaba la fila de crear y editar; ver sección 12.)*

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
| Historial de etapas | `his_` | `his_000045` |
| Actividad | `act_` | `act_000789` |
| Producto | `pro_` | `pro_000010` |
| Cotización | `cot_` | `cot_000321` |
| Notificación | `not_` | `not_000654` |
| Evento | `evt_` | `evt_000987` |

En los datos ficticios los números son secuenciales para que los servicios sean coherentes entre sí (una oportunidad debe apuntar a un `cliente_id` que **sí exista**). Al crear datos desde la aplicación, el identificador puede generarse de otra forma, pero **siempre con su prefijo y siempre como texto**. Los registros nuevos usan el prefijo de entidad más UUID hexadecimal completo; siguen admitiéndose los identificadores anteriores y los secuenciales del generador.

### Campos comunes en todas las tablas

`tenant_id`, `fecha_creacion` y `fecha_actualizacion` aparecen en todas las tablas principales. El `tenant_id` es la base del aislamiento: toda consulta se hace **dentro** de un tenant.

## 7. Los microservicios en detalle

Para cada servicio: qué hace, qué no hace, qué guarda, qué rutas ofrece y qué eventos publica o escucha. La base es **DynamoDB** (NoSQL) en todos los servicios. El enunciado permite elegir SQL o NoSQL según convenga a cada servicio, y elegimos DynamoDB porque es nativo de serverless, no hay un servidor de base de datos que administrar y el aislamiento por tenant se resuelve con el tenant\_id en la clave. Si algún servicio necesitara SQL, el enunciado exige un único RDS con el patrón Single Database, Multiple Schemas y presentar su diagrama entidad-relación. Con DynamoDB, cada tabla se presenta como estructura JSON en el informe; aquí se describe como lista de campos.

### 7.1 Usuarios y Tenants

**Estado:** diseñado e implementado; validación local parcial según sección 14. Verificación AWS pendiente de evidencia.

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

El candado de nombre, el de correo, el tenant, el primer admin y su evento pendiente se escriben en una sola transacción; todo se guarda o nada se guarda.

**Tabla `t_correos_locks`**: clave `correo` normalizado; campos `tenant_id`, `usuario_id`. Un correo queda reservado globalmente mediante escritura condicional. No se ofrece cambio de correo ni eliminación física de usuarios; desactivar no libera el correo. Antes de habilitar las nuevas escrituras sobre una instalación existente, ejecutar la migración de integridad con escrituras pausadas.

**Gestión de admins:** un admin no puede desactivarse ni quitarse su rol. Al cambiar otro usuario, la transacción comprueba que el solicitante sigue activo y con rol admin; esto impide que dos admins se desactiven mutuamente. Error propio: 409 `autoproteccion_admin`.

**Tabla `t_usuarios`**

| Campo | Descripción |
| --- | --- |
| `tenant_id` | A qué empresa pertenece |
| `usuario_id` | Identificador del usuario |
| `nombre` | Nombre completo |
| `correo` | Correo de acceso. **Decisión:** único en todo el sistema, para que el login solo pida correo y contraseña |
| `contrasena_hash` | Hash PBKDF2 con sal y parámetros (nunca texto plano; no es cifrado reversible) |
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

**Implementado:** Usuarios guarda `usuario.creado` en su outbox transaccional; el publicador programado lo envía al SNS compartido. Notificaciones aún no existe. **AWS pendiente:** comprobar publicación, reintento, atributo `tipo` y consumo cuando esté implementado.

### 7.2 Clientes

**Estado:** diseñado e implementado; validación local parcial según sección 14. Verificación AWS pendiente de evidencia.

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

**Eventos:** guarda `cliente.creado` en el outbox junto con el cliente y lo publica de forma diferida. No escucha eventos. **AWS pendiente:** verificar publicación y consumo cuando exista Notificaciones.

**Borrado lógico:** DELETE conserva el cliente con `eliminado: true`, `fecha_eliminacion`, `estado: inactivo` y `fecha_actualizacion`. Conserva los contactos; no elimina datos de otros servicios ni publica un evento. La consulta individual, edición y operaciones de contactos responden 404 para un cliente archivado. Los listados excluyen registros con `fecha_eliminacion`; una página puede estar vacía y aun tener `siguiente`, porque DynamoDB filtra después de evaluar el límite. El consumidor debe continuar mientras haya cursor.

**Contacto principal:** `t_clientes.contacto_principal_id` es un campo técnico opcional. Crear un contacto principal reserva ese campo y guarda el contacto en una sola transacción; si ya hay principal, devuelve 409 `contacto_principal_existente`. No existe todavía una ruta para cambiar el principal. `es_principal` solo admite booleanos. El script de migración detecta duplicados previos y exige resolverlos antes de aplicar.

**Filtro de responsable:** `GET /clientes?responsable_id=usr_...`, usando el GSI `responsable_id-index` (`tenant_id` + `responsable_id`, proyección completa). Conservar el filtro durante la paginación.

### 7.3 Oportunidades

**Estado:** diseñado e implementado; validación local parcial según sección 14. Verificación AWS pendiente de evidencia.

**Qué hace:** gestiona el pipeline de ventas. Registra cada oportunidad, su monto, su etapa y el historial de cambios de etapa. Es el servicio central del CRM.

**Qué NO hace:** no guarda datos del cliente (solo su `cliente_id` y una copia opcional de su nombre para mostrar en listas), ni cotizaciones, ni tareas. No consulta la base de Clientes, así que **no valida que el `cliente_id` exista** (solo que sea texto no vacío).

**Etapas del pipeline** (valores fijos, en este orden):

`nueva` → `calificada` → `propuesta` → `en_negociacion` → `ganada` o `perdida`

**Reglas de negocio:**

- Al crear, la etapa es siempre `nueva`.
- **Las etapas solo avanzan** y pueden saltarse (por ejemplo, de `nueva` a `propuesta`). No se retrocede. Desde cualquier etapa abierta se puede pasar a `perdida`.
- `ganada` y `perdida` son finales: una oportunidad cerrada **no se reabre, no se edita y no cambia de etapa** (409 `oportunidad_cerrada`).
- Al marcar `perdida` es obligatorio indicar `motivo_perdida` no vacío (400 `motivo_requerido`).
- `ganada` puede fijarse **manualmente** (cambio de etapa por un usuario) o **automáticamente** cuando llega el evento `cotizacion.aceptada`.
- **Probabilidad:** si no se envía, se asigna según la etapa. En cada cambio de etapa se recalcula según la etapa nueva. Al crear o editar también se puede enviar manualmente (0 a 100).

| Etapa | `nueva` | `calificada` | `propuesta` | `en_negociacion` | `ganada` | `perdida` |
| --- | :-: | :-: | :-: | :-: | :-: | :-: |
| Probabilidad por defecto | 10 | 25 | 50 | 75 | 100 | 0 |

- **Permisos:** vendedor, gerente y admin pueden ver, crear, editar y cambiar de etapa. Solo gerente y admin pueden **eliminar** y **reasignar** `responsable_id`. Un vendedor que intente asignar otro responsable al crear, o reasignar al editar, recibe 403 `prohibido`. Si `responsable_id` no se envía al crear, se usa el `usuario_id` del token.
- **Concurrencia:** el cambio de etapa se hace en una sola transacción (actualizar la oportunidad + guardar el historial) con la condición de que la etapa siga siendo la que se leyó. Si otro cambio se adelantó, responde 409 `conflicto_etapa`.
- **Validaciones numéricas:** `monto_estimado` debe ser un número entre 0 y 1,000,000,000,000; `probabilidad`, un número entre 0 y 100. No se aceptan valores booleanos, `NaN` ni infinitos. `moneda` solo admite `PEN` o `USD` (por defecto `PEN`).

**Tabla `t_oportunidades`** (clave: `tenant_id` + `oportunidad_id`)

| Campo | Descripción |
| --- | --- |
| `tenant_id`, `oportunidad_id` | Identificación (`opo_` + UUID hexadecimal) |
| `cliente_id` | Cliente al que se le intenta vender |
| `cliente_nombre` | *(opcional)* Copia del nombre del cliente para mostrar listas sin consultar Clientes. No se mantiene sincronizada si el cliente cambia de nombre |
| `titulo` | Descripción corta |
| `monto_estimado`, `moneda` | Valor estimado de la venta (número) y su moneda (`PEN`, `USD`) |
| `etapa` | Una de las etapas del pipeline |
| `probabilidad` | Número de 0 a 100 |
| `fecha_cierre_estimada` | *(opcional)* Cuándo se espera cerrar (ISO 8601) |
| `responsable_id` | `usuario_id` del vendedor a cargo |
| `motivo_perdida` | Solo si está `perdida` |
| `fecha_creacion`, `fecha_actualizacion` | Fechas |

Índices secundarios (GSI, todos con proyección completa) para filtrar dentro del tenant:

| Índice | Clave | Para qué |
| --- | --- | --- |
| `cliente_id-index` | `tenant_id` + `cliente_id` | Oportunidades de un cliente |
| `responsable_id-index` | `tenant_id` + `responsable_id` | "Mis oportunidades" |
| `etapa-index` | `tenant_id` + `etapa` | Oportunidades de una etapa (tablero del pipeline) |

**Tabla `t_historial_etapas`** (clave: `tenant_id` + `historial_id`)

| Campo | Descripción |
| --- | --- |
| `tenant_id`, `historial_id` | Identificación (`his_` + UUID hexadecimal) |
| `oportunidad_id` | A qué oportunidad pertenece |
| `etapa_anterior`, `etapa_nueva` | Cambio realizado |
| `usuario_id` | Quién lo hizo. Vale `sistema` cuando el cambio lo hizo el consumidor de `cotizacion.aceptada` |
| `fecha_cambio` | Cuándo |

Índice `oportunidad_id-index`: `tenant_id` + `oportunidad_id` (historial de una oportunidad).

Los montos se guardan como número decimal en DynamoDB y se devuelven como número JSON (entero si no tiene decimales). Las oportunidades archivadas se excluyen del listado y de las consultas/ediciones habituales (404). Se conserva el historial almacenado para auditoría; la ruta de historial requiere una oportunidad no archivada. Un listado filtrado puede devolver una página vacía con cursor: continuar mientras haya `siguiente`.

**Rutas principales** (todas protegidas)

| Ruta | Lambda | Para qué |
| --- | --- | --- |
| `POST /oportunidades` | `CrearOportunidad` | Crea la oportunidad en etapa `nueva`. Requeridos: `cliente_id`, `titulo`, `monto_estimado`. Opcionales: `moneda`, `probabilidad`, `fecha_cierre_estimada`, `responsable_id`, `cliente_nombre`. Responde 201 con `oportunidad_id` |
| `GET /oportunidades` | `ListarOportunidades` | Lista del tenant con paginación (`limite` 1 a 100, por defecto 50; `siguiente`). Filtro opcional de **un solo** campo: `cliente_id`, `responsable_id` o `etapa`. Más de uno → 400 `filtros_incompatibles`. Respuesta `{"oportunidades": [...], "siguiente": ...}` |
| `GET /oportunidades/{oportunidad_id}` | `ObtenerOportunidad` | Devuelve `{"oportunidad": {...}}` o 404 |
| `PUT /oportunidades/{oportunidad_id}` | `ActualizarOportunidad` | Edita `titulo`, `monto_estimado`, `moneda`, `probabilidad`, `fecha_cierre_estimada`, `responsable_id`, `cliente_nombre`. **No** permite cambiar `etapa` ni `cliente_id` (400 `campo_no_editable`). No aplica a oportunidades cerradas |
| `PUT /oportunidades/{oportunidad_id}/etapa` | `CambiarEtapa` | Body: `etapa` y, si es `perdida`, `motivo_perdida` |
| `GET /oportunidades/{oportunidad_id}/historial` | `ListarHistorial` | Cambios de etapa ordenados por `fecha_cambio` ascendente. Sin paginación. 404 si la oportunidad no existe en el tenant |
| `DELETE /oportunidades/{oportunidad_id}` | `EliminarOportunidad` | Solo gerente o admin. Archiva la oportunidad con `eliminado: true` y `fecha_eliminacion`, conservando el historial. **No publica evento** |

**Códigos de error propios de este servicio** (todos con formato `{"codigo": "...", "mensaje": "..."}`):

| HTTP | `codigo` | Cuándo |
| --- | --- | --- |
| 400 | `json_invalido` | El body no es un JSON válido (o no es un objeto) |
| 400 | `datos_incompletos` | Faltan campos obligatorios |
| 400 | `datos_invalidos` | Un campo tiene tipo o rango incorrecto (monto, probabilidad, moneda, fecha, textos vacíos) |
| 400 | `campo_no_editable` | Se intenta cambiar `etapa` o `cliente_id` con `PUT /oportunidades/{id}` |
| 400 | `etapa_invalida` | La etapa no existe |
| 400 | `transicion_invalida` | Retroceder o repetir etapa |
| 400 | `motivo_requerido` | Pasar a `perdida` sin `motivo_perdida` |
| 400 | `filtros_incompatibles` | Más de un filtro en el listado |
| 400 | `paginacion_invalida` | El valor de `siguiente` no corresponde a la consulta (por ejemplo, se cambió el filtro entre páginas) |
| 403 | `prohibido` | Rol insuficiente (eliminar, reasignar responsable) |
| 404 | `no_encontrado` | La oportunidad no existe en el tenant del token |
| 409 | `oportunidad_cerrada` | Editar o cambiar de etapa una oportunidad `ganada` o `perdida` |
| 409 | `conflicto_etapa` | Otro cambio de etapa se adelantó; reintentar |

**Eventos que produce** (guardados en el outbox junto con el cambio de negocio, y publicados por el proceso programado; formato de sección 8):

- `oportunidad.creada` al crear.
- `oportunidad.etapa_cambiada` en un cambio entre etapas **abiertas**.
- `oportunidad.ganada` al cerrar como ganada (manualmente o por `cotizacion.aceptada`).
- `oportunidad.perdida` al cerrar como perdida.

**Regla de cierre:** al cerrar una oportunidad se publica **solo** `ganada` o `perdida`, nunca además `etapa_cambiada`, para que Actividades no reciba dos eventos del mismo cambio. Los montos viajan como número, no como texto.

**Eventos que escucha:** `cotizacion.aceptada`.

**Cómo consume `cotizacion.aceptada`:**

1. Una cola SQS propia (con cola de errores DLQ tras 3 intentos) recibe una copia del evento. La suscripción al topic filtra por el atributo `tipo = cotizacion.aceptada` y la cola solo acepta mensajes de ese topic.
2. El consumidor toma el `tenant_id` **del evento** y el `oportunidad_id` de `datos`.
3. Si la oportunidad no existe, está archivada o ya está cerrada, lo registra y sigue (idempotente, porque SQS entrega al menos una vez).
4. Si está abierta, pasa a `ganada`, guarda historial con `usuario_id = sistema` y guarda el evento `oportunidad.ganada` en una misma transacción. El publicador programado envía después el evento. Si se reentrega el mensaje, el cierre existente evita repetir historial y evento.
5. Si hay un conflicto de etapa o un error inesperado, el mensaje se reintenta y, tras 3 intentos, va a la DLQ.

Esta reacción produce únicamente `oportunidad.ganada`, mediante el outbox; no produce además `oportunidad.etapa_cambiada`.

**\[VERIFICAR\]** Es el primer servicio con consumidor SQS. Al desplegar, comprobar primero que la política de la cola y la suscripción con su filtro dejan pasar el mensaje, antes de probar el resto. Mientras no exista Cotizaciones, se puede probar publicando a mano en el topic un evento `cotizacion.aceptada` con el atributo `tipo` y un `oportunidad_id` real.

### 7.4 Actividades

**Estado:** diseño inicial; no implementado ni verificado en AWS. Las rutas y eventos siguientes son el contrato previsto.

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

**Estado:** diseño inicial; no implementado ni verificado en AWS. Las rutas y eventos siguientes son el contrato previsto.

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

**Importante para este servicio:** al publicar en SNS debe incluir el atributo de mensaje `tipo` con el nombre del evento (como hacen Usuarios, Clientes y Oportunidades). Sin ese atributo, el filtro de la suscripción de Oportunidades descarta `cotizacion.aceptada` sin dar ningún error.

### 7.6 Notificaciones

**Estado:** implementado; validado localmente; pendiente de evidencia en AWS.

**Qué hace:** escucha eventos de los demás servicios y registra avisos para los usuarios. Los usuarios consultan sus avisos y los marcan como leídos.

**Qué NO hace:** no decide ni cambia nada en el negocio. Solo reacciona.

**Tabla `t_notificaciones`**: un aviso por evento y destino.

| Campo | Descripción |
| --- | --- |
| `tenant_id`, `notificacion_id` | Identificación. `notificacion_id` = `not_` + 32 caracteres hexadecimales derivados de `tenant_id`, `evento_id` y destino |
| `usuario_destino_id` | Usuario al que va dirigido (solo en avisos a un usuario) |
| `rol_destino` | Rol al que va dirigido (solo en avisos a un rol) |
| `destino` | Interno, para el GSI: `<tenant_id>#usr#<usuario_id>` o `<tenant_id>#rol#<rol>` |
| `orden` | Interno, para el GSI: `<fecha_creacion>#<notificacion_id>` |
| `tipo`, `titulo`, `mensaje`, `evento_id`, `fecha_creacion` | Contenido del aviso y evento que lo originó |

GSI `destino-index`: `destino` + `orden`, proyección completa.

**Tabla `t_lecturas_notificaciones`**: una fila por (aviso, usuario) que lo marcó como leído. Clave `tenant_id` + `lectura_id` (`<notificacion_id>#<usuario_id>`); campos `notificacion_id`, `usuario_id`, `fecha_lectura`. El campo `leida` de la respuesta se calcula por usuario, así que un gerente que lee un aviso dirigido a `gerente` no lo marca como leído para los demás gerentes.

**Deduplicación:** el `notificacion_id` es determinista y se escribe con `attribute_not_exists`. Una reentrega del mismo evento no crea otro aviso ni reinicia lecturas.

**Destinatarios por evento:** `usuario.creado` → `usuario_id`; `cliente.creado`, `oportunidad.creada`, `oportunidad.etapa_cambiada`, `actividad.completada` → `responsable_id`; `oportunidad.ganada`, `oportunidad.perdida` → `responsable_id` y rol `gerente`; `cotizacion.enviada`, `cotizacion.rechazada` → `creada_por`; `cotizacion.aceptada` → rol `gerente`. Si falta el usuario en `datos`, se omite ese destinatario.

**Rutas:** `GET /notificaciones` (parámetros `limite` 1-100, `solo_no_leidas=true`, `siguiente`; responde `notificaciones`, `no_leidas_en_pagina` y `siguiente`); `PUT /notificaciones/{notificacion_id}/leer` (idempotente; 404 `no_encontrado` si el aviso no existe o no está dirigido al usuario ni a su rol).

**Infraestructura:** cola `<stage>-notificaciones` con DLQ `<stage>-notificaciones-dlq` (3 intentos), política que solo permite escribir al topic compartido y suscripción filtrada por `tipo` con los 10 eventos del catálogo, sin entrega en bruto (el consumidor lee el sobre SNS).

**Límites:** con `solo_no_leidas=true` el filtro se aplica sobre la página, que puede venir con menos elementos; `no_leidas_en_pagina` no es un total global.

**Decisión de diseño:** como Notificaciones no puede consultar la base de Usuarios, un aviso se dirige a un usuario concreto (cuando el evento trae su `usuario_id`, como `responsable_id`) **o a un rol** (por ejemplo, todos los gerentes del tenant). Al consultar, cada usuario ve los avisos dirigidos a él o a su rol.

**Rutas principales:** `GET /notificaciones`, `PUT /notificaciones/{notificacion_id}/leer`.

**Eventos:** no publica ninguno. Escucha todos los del catálogo (sección 8).

## 8. Eventos: cómo se hablan los servicios

Un servicio **publica** un anuncio en **SNS** (el altavoz). Cada servicio interesado tiene su **cola SQS** (el buzón) y recibe una copia. Quien publica no sabe quién escucha.

### Publicación confiable implementada: outbox por servicio

Usuarios, Clientes y Oportunidades tienen cada uno su tabla `t_eventos_<servicio>` (el nombre desplegado lleva el stage). No se comparte la tabla entre servicios.

| Campo | Uso |
| --- | --- |
| `evento_id` | Clave de la tabla; se conserva en todos los reintentos |
| `tenant_id` | Tenant del evento |
| `estado` | `pendiente` o `enviado` |
| `fecha_creacion` | Fecha UTC del evento |
| `evento` | Sobre completo con `datos` |
| `expira_en` | TTL numérico, solo para enviados; limpieza después de 7 días |

El GSI `estado-fecha-index` usa `estado` + `fecha_creacion` y proyección completa. El dato de negocio y el evento pendiente se escriben en una transacción de DynamoDB. Cada servicio configura un publicador de la capa común (`crm_comun.eventos.lambda_handler`), ejecutado cada minuto y con concurrencia reservada 1. Consulta los pendientes, publica en SNS con atributo `tipo`, y solo tras éxito marca `enviado`. Un fallo mantiene el evento pendiente sin TTL, para reintentar. La latencia normal incluye el intervalo del publicador y la consistencia eventual del índice; no es publicación inmediata ni un SLA.

**Semántica:** entrega al menos una vez, sin orden global garantizado. Si SNS recibe el mensaje y falla el marcado de enviado, se publicará otra vez con el mismo `evento_id`. Los consumidores futuros deben deduplicar por `tenant_id` + `evento_id` y destino cuando corresponda. Oportunidades evita un segundo cierre porque la etapa final se confirma atómicamente. No hay consumidores de Actividades o Notificaciones implementados todavía. Al desplegar, verificar permisos de EventBridge, concurrencia reservada, transacciones y acceso a las tablas con LabRole. Supervisar eventos pendientes y errores del publicador; alarmas operativas aún pendientes.

### Formato común de todo evento

| Campo | Descripción |
| --- | --- |
| `evento_id` | Identificador único del evento (`evt_` + UUID hexadecimal) |
| `tipo` | Nombre del evento, por ejemplo `oportunidad.ganada` |
| `tenant_id` | A qué empresa pertenece (**siempre presente**) |
| `fecha` | Cuándo ocurrió |
| `datos` | Información propia de cada evento (ver tabla) |

Además, todo mensaje se publica con el atributo de mensaje SNS `tipo` (mismo valor que el campo `tipo`), porque las suscripciones filtran por él. Quien consume recibe el evento dentro del sobre de SNS: el cuerpo del mensaje SQS trae un campo `Message` que contiene el evento como texto JSON.

### Catálogo de eventos

| Evento | Lo publica | Lo escuchan | Qué hacen | `datos` que lleva |
| --- | --- | --- | --- | --- |
| `usuario.creado` | Usuarios | Notificaciones | Aviso de bienvenida | `usuario_id`, `nombre`, `rol` |
| `cliente.creado` | Clientes | Notificaciones | Avisa al responsable | `cliente_id`, `nombre`, `responsable_id` |
| `oportunidad.creada` | Oportunidades | Notificaciones | Avisa al responsable | `oportunidad_id`, `cliente_id`, `titulo`, `monto_estimado`, `responsable_id` |
| `oportunidad.etapa_cambiada` | Oportunidades (solo cambios entre etapas abiertas) | Actividades, Notificaciones | Actividades crea un seguimiento automático; Notificaciones avisa | `oportunidad_id`, `cliente_id`, `etapa_anterior`, `etapa_nueva`, `responsable_id` |
| `oportunidad.ganada` | Oportunidades (al cerrar, manual o por `cotizacion.aceptada`) | Actividades, Notificaciones | Actividades crea tarea de entrega/inicio; Notificaciones avisa al gerente y al responsable | `oportunidad_id`, `cliente_id`, `titulo`, `monto_estimado`, `responsable_id` |
| `oportunidad.perdida` | Oportunidades (al cerrar) | Actividades, Notificaciones | Actividades cancela tareas pendientes de esa oportunidad; Notificaciones avisa | `oportunidad_id`, `cliente_id`, `motivo_perdida`, `responsable_id` |
| `cotizacion.enviada` | Cotizaciones | Actividades, Notificaciones | Actividades crea seguimiento a unos días; Notificaciones avisa | `cotizacion_id`, `oportunidad_id`, `cliente_id`, `total`, `creada_por` |
| `cotizacion.aceptada` | Cotizaciones | Oportunidades, Notificaciones | Oportunidades la marca como `ganada` (y publica `oportunidad.ganada`); Notificaciones avisa | `cotizacion_id`, `oportunidad_id`, `cliente_id`, `total` |
| `cotizacion.rechazada` | Cotizaciones | Notificaciones | Avisa al responsable | `cotizacion_id`, `oportunidad_id`, `cliente_id`, `creada_por` |
| `actividad.completada` | Actividades | Notificaciones | Avisa al responsable de la oportunidad (opcional) | `actividad_id`, `oportunidad_id`, `responsable_id` |

**Regla de cierre de oportunidades:** al cerrar una oportunidad solo se publica `oportunidad.ganada` u `oportunidad.perdida`; **nunca además** `oportunidad.etapa_cambiada`. Así, Actividades y Notificaciones no procesan dos eventos por el mismo cambio. En los eventos de Oportunidades, los montos viajan como número, no como texto.

**Opcional si sobra tiempo:** aviso de tarea por vencer. Requiere una revisión programada, así que queda fuera de la versión base.

### Quién escucha a quién (resumen)

- **Notificaciones** escucha todo.
- **Actividades** escucha cambios de oportunidades y envíos de cotizaciones.
- **Oportunidades** escucha solo `cotizacion.aceptada`.
- **Usuarios** y **Clientes** no escuchan nada.

Cuidado con los ciclos: Oportunidades escucha una cotización aceptada y publica `oportunidad.ganada`; esa cadena es intencional y **termina ahí**. Nadie debe publicar un evento como reacción a un evento que lo originó a él mismo.

## 9. Flujos de uso

Estos flujos describen el comportamiento objetivo; no son evidencia de implementación ni de ejecución. Incluyen servicios todavía pendientes (ver inventario de sección 0). Son la base de la demo y de las pruebas. Cada integrante debe poder explicar el flujo donde participa su servicio.

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
2. Avanza la oportunidad por `calificada`, `propuesta` y `en_negociacion` (puede saltarse etapas, pero no retroceder). En cada cambio entre etapas abiertas se publica `oportunidad.etapa_cambiada`, Actividades crea un seguimiento automático y el historial guarda el cambio.
3. Un integrante de ventas arma una cotización con los productos del catálogo y la envía (`cotizacion.enviada`). Actividades programa un seguimiento y se notifica al equipo.
4. El cliente acepta. Se marca la cotización como aceptada (`cotizacion.aceptada`).
5. Oportunidades escucha el evento, marca la oportunidad como `ganada` (el historial registra el cambio con usuario `sistema`) y publica `oportunidad.ganada`. Como es un cierre, no se publica además `oportunidad.etapa_cambiada`.
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
- **Oportunidad cerrada:** se intenta editar o cambiar de etapa una oportunidad `ganada` o `perdida`. Se rechaza (409 `oportunidad_cerrada`).

### Flujo 9: Demo con 2 tenants

1. Login como admin de `ten_seguros` y como admin de `ten_electro`.
2. Mostrar que cada uno ve únicamente sus clientes, oportunidades y avisos.
3. Ejecutar el Flujo 4 en un tenant y mostrar que el otro no se entera.
4. Ejecutar el Flujo 8 para demostrar el aislamiento y la protección.

## 10. Datos ficticios

- Mínimo **30,000 registros por microservicio**, repartidos en los 3 tenants (unos 10,000 por tenant). **Decisión registrada:** tabla principal de cada servicio con 30,000 o más: `t_usuarios`, `t_clientes`, `t_oportunidades`, `t_actividades`, `t_cotizaciones` (con `t_productos` en su misma base) y `t_notificaciones`.
- **Los datos deben ser coherentes entre servicios:** toda oportunidad apunta a un `cliente_id` que existe en el mismo tenant; toda cotización a una oportunidad existente; todo `responsable_id` a un usuario existente.
- Por eso el orden de generación es: usuarios y tenants, luego clientes, luego oportunidades, luego actividades y cotizaciones, luego notificaciones. **Una sola persona** genera todos los datos con un mismo programa para garantizar coherencia.
- La cantidad de usuarios por tenant (10,000) es poco realista, pero cumple el mínimo. La distribución figura aprobada en la sección 13; conservar la evidencia del acuerdo del grupo y verificar el cumplimiento del enunciado con el profesor.
- **Estado:** generación y carga masiva todavía no implementadas. El futuro generador debe importar `crm_comun.contrasenas.crear_hash` (agregando `compartido/capa_comun/python` a `PYTHONPATH`), crear los candados de correo y mantener coherente `contacto_principal_id`. El único script de datos funcional por ahora es `datos/migrar_integridad.py`.
- **Para Oportunidades:** el generador (`datos/generar_datos.py`) debe respetar las reglas del servicio: `monto_estimado` numérico con `moneda` `PEN` o `USD`; `probabilidad` coherente con la etapa; `motivo_perdida` solo en las `perdida`; y, si se carga `t_historial_etapas`, que cada oportunidad tenga cambios de etapa coherentes con su etapa actual (`usuario_id` de un usuario existente). `cliente_nombre` es opcional.
- **Para Notificaciones:** cada aviso generado debe incluir `destino` y `orden` con el formato de la sección 7.6; sin ellos no aparece en `GET /notificaciones`. Los avisos deben apuntar a usuarios existentes del mismo tenant. Las lecturas, si se generan, van en `t_lecturas_notificaciones`.

## 11. Cómo trabajamos como grupo

### Repositorio y código

- **Un solo repositorio público** de GitHub con una carpeta por servicio (`usuarios`, `clientes`, `oportunidades`, `actividades`, `productos_cotizaciones`, `notificaciones`), una carpeta para el authorizer y las piezas compartidas, y otra para el frontend.
- Cada avance se sube con frecuencia, aunque esté a medias. **Si no está en el repositorio, para el grupo no existe.**
- Nada de claves ni credenciales en el repositorio.

### Despliegue

- Cada integrante tiene su propia cuenta de AWS, así que **cada quien despliega su propia copia** con el mismo código y la misma configuración de Serverless Framework.
- Cada servicio tiene su propio archivo de configuración de Serverless Framework.
- Nombres de recursos definidos en `serverless.yml`: servicios `crm-compartido`, `crm-usuarios`, `crm-clientes`, `crm-oportunidades`; tablas con prefijo `${sls:stage}-`. Usar el mismo stage al desplegar todos los stacks de una cuenta (por ejemplo `dev`). Región actual `us-east-1`, runtime Python 3.14, Framework 4 y LabRole de AWS Academy.
- **Prueba temprana obligatoria:** antes de programar nada serio, todos despliegan un ejemplo mínimo para confirmar que pueden hacerlo en sus cuentas de AWS Academy.
- Para la demo, un solo integrante despliega todo en su cuenta.
- **Orden de despliegue:** primero `compartido` (authorizer, capas y topic SNS), luego Usuarios, Clientes y Oportunidades. Cada servicio lee los outputs del compartido. Tras cambiar una capa, volver a desplegar los servicios para usar la versión nueva. En instalación nueva el Authorizer rechaza hasta que existan las tablas y la identidad. Para actualizar datos existentes, pausar escrituras, desplegar y ejecutar la migración antes de reabrir. Ver [validación y despliegue](validacion_local.md).

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

El historial conserva decisiones anteriores aunque luego hayan sido reemplazadas. El contrato vigente está en las secciones 0, 5, 7 y 8; por ejemplo, el borrado físico y los IDs de 8 caracteres de las entradas del 10-nov fueron sustituidos el 11-nov.

Cualquier cambio de nombres, campos, rutas o eventos se documenta aquí junto con el código antes de integrar la contribución, y se comunica al grupo. Quien necesite algo de otro servicio lo pide a su responsable y se registra en esta sección.

| Fecha | Qué cambió | Quién |
| --- | --- | --- |
| 2026-11-11 | **Notificaciones:** tablas `t_notificaciones` (GSI `destino-index`) y `t_lecturas_notificaciones`; deduplicación por `tenant_id` + `evento_id` + destino; lectura individual por usuario; cola + DLQ + suscripción filtrada; rutas GET y PUT; destinatarios por evento (sección 7.6). | Mathias |    
| 2026-11-11 | Corrección de importaciones; capa común HTTP/claims; PBKDF2 con migración en login; Authorizer con estado/rol vigente y JWT nuevo de 1h; transacciones de alta y candado global de correo; protección de admins también ante cambios simultáneos; validación de responsables y contacto principal atómico; borrado lógico de Clientes/Oportunidades; outbox transaccional con reintentos; GSI de responsable; Framework 4 y configuración compartida sin org personal. Se añadieron migración de integridad y pruebas locales. | Implementación asistida; revisión del grupo pendiente |
| 2026-11-11 | Documento reorganizado para distinguir diseñado, implementado, validado localmente y verificado en AWS; inventario, registro de correcciones, límites y matriz de evidencias. Próximo servicio: Notificaciones. | Implementación asistida; revisión del grupo pendiente |
| 2026-11-04 | Candado `t_tenants_locks` y campo `nombre_normalizado` para no duplicar empresas. Advertencias a verificar: 401 vs 403 del authorizer, hash SHA-256, eventos SNS sin consumidores todavía. | Castro |
| 2026-11-10 | **Oportunidades – ruta nueva:** `DELETE /oportunidades/{oportunidad_id}` (solo gerente/admin; borra el historial y la oportunidad; no publica evento). Sale de la matriz de permisos, pero no estaba en la lista de rutas. Se agregó la fila "Cambiar la etapa de una oportunidad" a la matriz (sin cambiar permisos). | Castro |
| 2026-11-10 | **Oportunidades – campo nuevo:** `cliente_nombre` (opcional) en `t_oportunidades`, para mostrar listas en el FrontEnd sin consultar Clientes. | Castro |
| 2026-11-10 | **Oportunidades – prefijo nuevo:** `his_` para el historial de etapas (`t_historial_etapas`). | Castro |
| 2026-11-10 | **Oportunidades – eventos:** al cerrar una oportunidad se publica solo `oportunidad.ganada` u `oportunidad.perdida`, nunca además `oportunidad.etapa_cambiada`, para que Actividades no cree dos tareas por el mismo cambio. Los montos viajan como número. Se agregó el atributo `tipo` y el sobre SNS al formato de eventos (sección 8). | Castro |
| 2026-11-10 | **Oportunidades – reglas:** las etapas solo avanzan (pueden saltarse); probabilidad por defecto por etapa (10, 25, 50, 75, 100, 0) y recalculada en cada cambio; `ganada` también se puede fijar manualmente, no solo por `cotizacion.aceptada`; oportunidad cerrada no se edita ni cambia de etapa; `moneda` limitada a `PEN` y `USD`; `monto_estimado` entre 0 y 10¹²; `fecha_cierre_estimada` en ISO 8601; editar con `etapa` o `cliente_id` responde 400 `campo_no_editable`; no se valida que `cliente_id` exista. | Castro |
| 2026-11-10 | **Oportunidades – índices y datos:** GSI `cliente_id-index`, `responsable_id-index` y `etapa-index` en `t_oportunidades`; GSI `oportunidad_id-index` en `t_historial_etapas`; `usuario_id = "sistema"` en el historial cuando el cambio lo hace el consumidor de `cotizacion.aceptada`. | Castro |
| 2026-11-10 | **Oportunidades – códigos de error nuevos:** `json_invalido`, `datos_invalidos`, `campo_no_editable`, `etapa_invalida`, `transicion_invalida`, `motivo_requerido`, `oportunidad_cerrada`, `conflicto_etapa`, `filtros_incompatibles`, `paginacion_invalida` (ver 7.3). | Castro |
| 2026-11-10 | **Oportunidades – primer consumidor SQS:** cola + DLQ (3 intentos) + política que solo permite escribir al topic compartido + suscripción filtrada por `tipo = cotizacion.aceptada`, definidas en el `serverless.yml` del servicio. Cotizaciones debe publicar con el atributo `tipo`. | Castro |

## 13. Decisiones pendientes

- [x] Aprobar la matriz de permisos por rol (sección 5).
- [x] Confirmar que el correo es único en todo el sistema (sección 7.1).
- [x] Confirmar dónde se guarda la clave secreta del token en AWS Academy.
- [x] Confirmar qué 2 tenants se usan en la demo (sección 3).
- [x] Confirmar la distribución de los 30,000 registros por servicio (sección 10).
- [x] Confirmar que todos los servicios usan DynamoDB (el enunciado permite SQL o NoSQL por servicio).

## 14. Validación, pendientes y evidencia AWS

### Evidencia local

La validación local cubrió contratos HTTP, hashes, Authorizer, conflictos de registro/edición, protección de admins, contacto principal, borrado lógico, outbox, cierre de oportunidades, reentregas SQS y resolución de handlers/configuración. Usó dobles de prueba de boto3; **no demuestra transacciones reales, permisos, tiempos de ejecución ni integración AWS**. Se complementó con compilación y análisis estático. El código de pruebas y sus dependencias se mantienen fuera del remoto por ser material local; el resultado está descrito en [validacion_local.md](validacion_local.md).

### Matriz que debe completarse en AWS

Todos los casos están pendientes de evidencia en este documento. Al ejecutar, registrar fecha, responsable, cuenta/entorno, stage, pasos, resultado y enlace al registro o captura sin secretos.

| Caso | Resultado esperado | Estado AWS / evidencia |
| --- | --- | --- |
| Desplegar compartido y los tres servicios | Capas/importaciones, tablas, GSI, Authorizer y publicadores disponibles con LabRole | Pendiente |
| Auditar y aplicar migración sobre datos existentes | Ningún correo/principal duplicado; candados coherentes; rerun idempotente | Pendiente |
| Login nuevo y login con SHA-256 anterior | Token; hash antiguo migra a PBKDF2 sin cambiar contraseña | Pendiente |
| Token ausente, vencido o alterado | Sin token: 401; inválido/vencido: 403 según HTTP API; servicio no se ejecuta | Pendiente; el código local no acredita códigos de API Gateway |
| Usuario desactivado / rol cambiado / tenant suspendido | Token anterior rechazado en siguiente autorización; rol cambiado exige nuevo login | Pendiente |
| Altas simultáneas con mismo correo/nombre | Solo una exitosa; otra 409; ninguna fila parcial ni evento de alta fallida | Pendiente |
| Admin se desactiva o se degrada | 409; permanece activo/admin | Pendiente |
| Dos admins intentan desactivarse mutuamente | Una transacción pierde su condición; queda al menos un admin activo | Pendiente |
| JSON inválido y datos de tipo incorrecto | 400 con `codigo` y `mensaje` | Pendiente |
| Crear dos principales simultáneamente | Uno 201, otro 409; una sola referencia principal | Pendiente |
| Aislamiento y permisos con dos tenants | Listados separados; IDs ajenos 404; vendedor no elimina ni reasigna | Pendiente |
| Archivar cliente/oportunidad y recorrer listados | Referencias conservadas; archivados no visibles; paginación continúa aun si una página queda vacía | Pendiente |
| Caída temporal de SNS/publicador | Negocio y evento pendientes guardados; posterior publicación con mismo ID y atributo `tipo` | Pendiente |
| Cola SQS de Oportunidades y DLQ | Suscripción y política permiten SNS; 3 intentos; errores parciales solo reintentan fallidos | Pendiente |
| Publicar `cotizacion.aceptada` manualmente con atributo `tipo` | Cierre + historial `sistema` + evento pendiente `oportunidad.ganada`; reentrega no duplica cierre | Pendiente |
| Notificaciones: evento real de Usuarios/Clientes | Aviso visible para el destinatario tras el intervalo del publicador; reentrega no duplica | Pendiente |
| Notificaciones: aviso a rol y lectura individual | Dos gerentes ven el aviso; uno lo lee y el otro lo sigue viendo como no leído | Pendiente |
| Notificaciones: mensaje dañado | 3 intentos y luego DLQ; el resto del lote se procesa | Pendiente |

### Trabajo funcional pendiente

- [x] **Notificaciones:** implementado (pendiente evidencia AWS).
- [ ] **Productos y Cotizaciones:** implementar catálogo, cálculos con decimal, transiciones, permisos y eventos; adoptar outbox y atributo SNS `tipo`.
- [ ] **Actividades:** CRUD, reglas y consumidores idempotentes; definir qué ocurre con seguimientos frente a eventos retrasados o fuera de orden.
- [ ] **Datos, frontend, informe y demo:** implementar generador/cargador coherentes y mínimo acordado de registros; integrar interfaz y documentar arquitectura/resultados.
- [ ] **Acuerdos del grupo:** responsables por servicio, hitos sin fecha y revisión de decisiones del 10-nov (etapas solo hacia adelante, saltos, ganada manual, probabilidad, tope de monto y campos no editables).

### Límites explícitos de la versión actual

- `cliente_nombre` es una instantánea opcional y puede quedar desactualizado. No hay sincronización automática.
- Los servicios guardan identificadores ajenos sin comprobar existencia en tablas de otros servicios. El frontend/generador debe usar referencias válidas del mismo tenant.
- Archivar conserva referencias pero no cancela actividades ni invalida cotizaciones: esos servicios aún no existen. No hay ruta de restauración ni purga.
- Las tablas de eventos proporcionan entrega al menos una vez; no orden global ni deduplicación automática en consumidores futuros. Aún faltan alarmas de acumulación de pendientes y DLQ.
- El Authorizer añade dos lecturas consistentes a cada autorización y rechaza si la base de identidad no está disponible. Una petición ya autorizada puede terminar tras una desactivación; un token aún vigente puede volver a servir si se reactiva al usuario con el mismo rol. No se implementa revocación permanente por sesión.
- PBKDF2 se ejecuta en los registros y en el login/migración. Medir latencia y memoria en Lambda antes de la demo; no hay medidas AWS en esta revisión.
- El candado de correo y el principal de contacto exigen migración previa sobre instalaciones existentes; el script no resuelve duplicados por sí solo y no se ha ejecutado en AWS.
- Los GSI y SNS/SQS tienen procesamiento asíncrono. Durante la propagación pueden observarse listados anteriores; los cambios usan condiciones/transacciones para proteger las escrituras.
- El cursor actual exige mantener los filtros entre páginas; no está firmado ni contiene el filtro original. Una paginación de producción necesitaría un cursor ligado a la consulta.
