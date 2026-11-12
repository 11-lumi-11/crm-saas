from src.utilidades import endpoint, obtener_claims, leer_actividad, publica, respuesta


@endpoint
def lambda_handler(event, context):
    tenant_id, _, _ = obtener_claims(event)
    actividad_id = (event.get('pathParameters') or {}).get('actividad_id')
    return respuesta(200, {'actividad': publica(leer_actividad(tenant_id, actividad_id))})
