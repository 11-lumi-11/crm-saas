from src.utilidades import (
    ErrorNegocio, manejar_errores, respuesta, obtener_claims, leer_cotizacion, exigir_estado,
    esta_vencida, cambiar_estado, generar_id
)


@manejar_errores
def lambda_handler(event, context):
    tenant_id, usuario_id, _ = obtener_claims(event)
    cotizacion_id = (event.get('pathParameters') or {}).get('cotizacion_id')

    cotizacion = leer_cotizacion(tenant_id, cotizacion_id)
    exigir_estado(cotizacion, 'enviada', 'aceptar')
    if esta_vencida(cotizacion):
        raise ErrorNegocio(409, 'cotizacion_vencida', 'La cotización ya venció; no se puede aceptar')

    solicitud_id = generar_id('sol')
    fecha = cambiar_estado(tenant_id, cotizacion_id, 'enviada', 'aceptacion_pendiente', 'cotizacion.aceptacion_solicitada', {
        'cotizacion_id': cotizacion_id,
        'oportunidad_id': cotizacion['oportunidad_id'],
        'cliente_id': cotizacion['cliente_id'],
        'solicitud_id': solicitud_id
    }, extra={'solicitud_aceptacion_id': solicitud_id, 'respondida_por': usuario_id,
              'resultado_aceptacion': ''})
    return respuesta(202, {'mensaje': 'Aceptación pendiente de confirmación; consulte la cotización.',
                           'cotizacion_id': cotizacion_id, 'estado': 'aceptacion_pendiente',
                           'fecha_solicitud': fecha})
