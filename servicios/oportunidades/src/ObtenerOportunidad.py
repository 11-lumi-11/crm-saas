from src.utilidades import manejar_errores, respuesta, obtener_claims, leer_oportunidad


@manejar_errores
def lambda_handler(event, context):
    tenant_id, _, _ = obtener_claims(event)
    oportunidad_id = (event.get('pathParameters') or {}).get('oportunidad_id')

    oportunidad = leer_oportunidad(tenant_id, oportunidad_id)
    return respuesta(200, {'oportunidad': oportunidad})
