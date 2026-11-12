from src.utilidades import manejar_errores, respuesta, obtener_claims, leer_producto


@manejar_errores
def lambda_handler(event, context):
    tenant_id, _, _ = obtener_claims(event)
    producto_id = (event.get('pathParameters') or {}).get('producto_id')
    return respuesta(200, {'producto': leer_producto(tenant_id, producto_id)})
