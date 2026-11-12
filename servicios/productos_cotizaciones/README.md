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

`borrador` → `enviada` → `aceptada` o `rechazada`. Solo se envía un borrador y solo se acepta o rechaza una enviada. Una cotización vencida (`fecha_vencimiento` pasada) no se envía ni se acepta (409 `cotizacion_vencida`). Cada transición actualiza la cotización y guarda el evento en el outbox en una sola transacción, con la condición de que el estado siga siendo el leído (409 `conflicto_estado` si otro cambio se adelantó).

## Eventos publicados

| Evento | Cuándo | `datos` |
| --- | --- | --- |
| `cotizacion.enviada` | borrador → enviada | `cotizacion_id`, `oportunidad_id`, `cliente_id`, `total`, `creada_por` |
| `cotizacion.aceptada` | enviada → aceptada | `cotizacion_id`, `oportunidad_id`, `cliente_id`, `total` |
| `cotizacion.rechazada` | enviada → rechazada | `cotizacion_id`, `oportunidad_id`, `cliente_id`, `creada_por` |

Se publican con el atributo SNS `tipo` (lo hace el publicador de la capa común). No escucha eventos.

## Probar la cadena con Oportunidades

1. Crear un producto (token de gerente o admin).
2. Crear una oportunidad en Oportunidades y copiar su `oportunidad_id`.
3. Crear la cotización con ese `oportunidad_id`, enviarla y aceptarla.
4. Esperar hasta un minuto (o invocar `publicarEventos` a mano) y consultar la oportunidad: debe estar `ganada`, con historial de usuario `sistema`.
