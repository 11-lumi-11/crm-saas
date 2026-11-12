from src.utilidades import manejar_errores, respuesta, obtener_claims, leer_cotizacion


@manejar_errores
def lambda_handler(event, context):
    tenant_id, _, _ = obtener_claims(event)
    cotizacion_id = (event.get('pathParameters') or {}).get('cotizacion_id')
    return respuesta(200, {'cotizacion': leer_cotizacion(tenant_id, cotizacion_id)})
