# Productos y Cotizaciones

Microservicio 5 del CRM. Catálogo de productos del tenant y cotizaciones para una oportunidad. Contrato completo en `docs/documento_base.md`, sección 7.5.

## Despliegue

Requiere el stack `crm-compartido` desplegado en el mismo stage (capa común, authorizer y topic SNS).

```sh
cd servicios/productos_cotizaciones
serverless deploy --stage dev
```

La URL que imprime el deploy es la de `VITE_PRODUCTOS_URL` (frontend) y `productos_url` (Postman). Productos y cotizaciones comparten la misma URL.

## Recursos

| Recurso | Nombre |
| --- | --- |
| Tabla catálogo | `<stage>-t_productos` (clave `tenant_id` + `producto_id`) |
| Tabla cotizaciones | `<stage>-t_cotizaciones` (clave `tenant_id` + `cotizacion_id`; GSI `oportunidad_id-index`, `estado-index`) |
| Outbox | `<stage>-t_eventos_productos_cotizaciones` (GSI `estado-fecha-index`, TTL `expira_en`) |
| Publicador | `publicarEventos` cada minuto, concurrencia reservada 1 (capa común) |

## Estados de una cotización

`borrador` → `enviada` → `aceptacion_pendiente` → `aceptada`; también se puede rechazar una cotización enviada. Una cotización vencida no se envía ni se solicita su aceptación (409 `cotizacion_vencida`).

`PUT /cotizaciones/{id}/aceptar` responde 202 y deja la cotización en `aceptacion_pendiente`. El usuario debe consultar `GET /cotizaciones/{id}` hasta conocer el resultado: si Oportunidades confirma el cierre, queda `aceptada`; si la oportunidad está perdida, ganada, archivada, no existe o pertenece a otro cliente, vuelve a `enviada` y el campo `resultado_aceptacion` explica el motivo. Mientras está pendiente no se puede archivar ni rechazar. Los mensajes circulan mediante outboxes y colas, por lo que pueden tardar varios minutos; una falla persistente requiere revisar las DLQ.

## Eventos publicados

| Evento | Cuándo | `datos` |
| --- | --- | --- |
| `cotizacion.enviada` | borrador → enviada | `cotizacion_id`, `oportunidad_id`, `cliente_id`, `total`, `creada_por` |
| `cotizacion.aceptacion_solicitada` | enviada → aceptación pendiente | `cotizacion_id`, `oportunidad_id`, `cliente_id`, `solicitud_id` |
| `cotizacion.aceptada` | enviada → aceptada | `cotizacion_id`, `oportunidad_id`, `cliente_id`, `total` |
| `cotizacion.rechazada` | enviada → rechazada | `cotizacion_id`, `oportunidad_id`, `cliente_id`, `creada_por` |

Se publican con el atributo SNS `tipo` (lo hace el publicador de la capa común). El servicio escucha `oportunidad.aceptacion_confirmada` y `oportunidad.aceptacion_rechazada` para terminar la solicitud.

## Probar la cadena con Oportunidades

1. Crear un producto (token de gerente o admin).
2. Crear una oportunidad en Oportunidades y copiar su `oportunidad_id`.
3. Crear la cotización con ese `oportunidad_id`, enviarla y aceptarla.
4. Consultar la cotización hasta que termine de estar pendiente y consultar la oportunidad: debe estar `ganada`, con historial de usuario `sistema`. El recorrido usa los publicadores de ambos servicios; no se garantiza que termine en un minuto.
