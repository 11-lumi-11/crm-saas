from src.utilidades import (
    ErrorNegocio, manejar_errores, respuesta, obtener_claims, leer_cotizacion, exigir_estado,
    esta_vencida, cambiar_estado
)


@manejar_errores
def lambda_handler(event, context):
    tenant_id, usuario_id, _ = obtener_claims(event)
    cotizacion_id = (event.get('pathParameters') or {}).get('cotizacion_id')

    cotizacion = leer_cotizacion(tenant_id, cotizacion_id)
    exigir_estado(cotizacion, 'enviada', 'aceptar')
    if esta_vencida(cotizacion):
        raise ErrorNegocio(409, 'cotizacion_vencida', 'La cotización ya venció; no se puede aceptar')

    # Oportunidades escucha este evento y marca la oportunidad como ganada
    fecha = cambiar_estado(tenant_id, cotizacion_id, 'enviada', 'aceptada', 'cotizacion.aceptada', {
        'cotizacion_id': cotizacion_id,
        'oportunidad_id': cotizacion['oportunidad_id'],
        'cliente_id': cotizacion['cliente_id'],
        'total': cotizacion['total']
    }, campos_fecha=('fecha_respuesta',), extra={'respondida_por': usuario_id})
    return respuesta(200, {'mensaje': 'Cotización aceptada', 'cotizacion_id': cotizacion_id,
                           'estado': 'aceptada', 'fecha_respuesta': fecha})
