from src.utilidades import (
    ErrorNegocio, manejar_errores, respuesta, leer_body, obtener_claims, cambiar_etapa
)


@manejar_errores
def lambda_handler(event, context):
    tenant_id, usuario_id, _ = obtener_claims(event)
    oportunidad_id = (event.get('pathParameters') or {}).get('oportunidad_id')
    body = leer_body(event)

    if body.get('etapa') is None:
        raise ErrorNegocio(400, 'datos_incompletos', 'Indique la etapa')

    oportunidad = cambiar_etapa(
        tenant_id, oportunidad_id, body['etapa'], body.get('motivo_perdida'), usuario_id
    )
    return respuesta(200, {
        'mensaje': 'Etapa actualizada correctamente',
        'oportunidad': oportunidad
    })
