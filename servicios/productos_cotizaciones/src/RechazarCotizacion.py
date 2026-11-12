from src.utilidades import (
    manejar_errores, respuesta, leer_body, obtener_claims, leer_cotizacion, exigir_estado,
    cambiar_estado, validar_texto_opcional
)


@manejar_errores
def lambda_handler(event, context):
    tenant_id, usuario_id, _ = obtener_claims(event)
    cotizacion_id = (event.get('pathParameters') or {}).get('cotizacion_id')
    body = leer_body(event)

    cotizacion = leer_cotizacion(tenant_id, cotizacion_id)
    exigir_estado(cotizacion, 'enviada', 'rechazar')

    extra = {'respondida_por': usuario_id}
    if body.get('motivo_rechazo') is not None:
        extra['motivo_rechazo'] = validar_texto_opcional(body['motivo_rechazo'], 'motivo_rechazo')

    # La oportunidad NO se pierde automáticamente (Flujo 5): solo se avisa
    fecha = cambiar_estado(tenant_id, cotizacion_id, 'enviada', 'rechazada', 'cotizacion.rechazada', {
        'cotizacion_id': cotizacion_id,
        'oportunidad_id': cotizacion['oportunidad_id'],
        'cliente_id': cotizacion['cliente_id'],
        'creada_por': cotizacion['creada_por']
    }, campos_fecha=('fecha_respuesta',), extra=extra)
    return respuesta(200, {'mensaje': 'Cotización rechazada', 'cotizacion_id': cotizacion_id,
                           'estado': 'rechazada', 'fecha_respuesta': fecha})
