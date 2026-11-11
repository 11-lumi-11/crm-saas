# Cambios propuestos al documento base por Notificaciones

Copiar cada bloque en su sección de `docs/documento_base.md` y borrar este archivo.

## Sección 0, inventario (reemplazar la fila de Notificaciones)

| Notificaciones | Sí | Consumidor SQS con DLQ, deduplicación por evento y destino, lectura individual por usuario, `GET /notificaciones` y `PUT /notificaciones/{notificacion_id}/leer` | Pruebas locales con boto3 simulado: sobre SNS, duplicados, aislamiento por tenant, lectura por rol, paginación y errores | Pendiente de evidencia |

## Sección 7.6 (reemplazar el bloque "Tabla `t_notificaciones`" y el "[DECIDIR]")

**Estado:** implementado; validado localmente; pendiente de evidencia en AWS.

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

## Sección 10 (agregar)

- **Para Notificaciones:** cada aviso generado debe incluir `destino` y `orden` con el formato de la sección 7.6; sin ellos no aparece en `GET /notificaciones`. Los avisos deben apuntar a usuarios existentes del mismo tenant. Las lecturas, si se generan, van en `t_lecturas_notificaciones`.

## Sección 12 (agregar fila)

| 2026-11-11 | **Notificaciones:** tablas `t_notificaciones` (GSI `destino-index`) y `t_lecturas_notificaciones`; deduplicación por `tenant_id` + `evento_id` + destino; lectura individual por usuario; cola + DLQ + suscripción filtrada; rutas GET y PUT; destinatarios por evento (sección 7.6). | Mathias |

## Sección 14 (marcar y agregar a la matriz)

- [x] **Notificaciones:** implementado (pendiente evidencia AWS).

| Notificaciones: evento real de Usuarios/Clientes | Aviso visible para el destinatario tras el intervalo del publicador; reentrega no duplica | Pendiente |
| Notificaciones: aviso a rol y lectura individual | Dos gerentes ven el aviso; uno lo lee y el otro lo sigue viendo como no leído | Pendiente |
| Notificaciones: mensaje dañado | 3 intentos y luego DLQ; el resto del lote se procesa | Pendiente |
