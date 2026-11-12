from src.utilidades import (
    ErrorNegocio, manejar_errores, respuesta, obtener_claims, leer_cotizacion, exigir_estado,
    esta_vencida, cambiar_estado
)


@manejar_errores
def lambda_handler(event, context):
    tenant_id, _, _ = obtener_claims(event)
    cotizacion_id = (event.get('pathParameters') or {}).get('cotizacion_id')

    cotizacion = leer_cotizacion(tenant_id, cotizacion_id)
    exigir_estado(cotizacion, 'borrador', 'enviar')
    if esta_vencida(cotizacion):
        raise ErrorNegocio(409, 'cotizacion_vencida', 'La cotización ya venció; cree una nueva')

    fecha = cambiar_estado(tenant_id, cotizacion_id, 'borrador', 'enviada', 'cotizacion.enviada', {
        'cotizacion_id': cotizacion_id,
        'oportunidad_id': cotizacion['oportunidad_id'],
        'cliente_id': cotizacion['cliente_id'],
        'total': cotizacion['total'],
        'creada_por': cotizacion['creada_por']
    }, campos_fecha=('fecha_envio',))
    return respuesta(200, {'mensaje': 'Cotización enviada', 'cotizacion_id': cotizacion_id,
                           'estado': 'enviada', 'fecha_envio': fecha})
