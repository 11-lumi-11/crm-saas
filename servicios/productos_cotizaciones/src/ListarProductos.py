from boto3.dynamodb.conditions import Key, Attr

from src.utilidades import (
    manejar_errores, respuesta, obtener_claims, tabla, leer_limite, validar_estado_producto
)


@manejar_errores
def lambda_handler(event, context):
    tenant_id, _, _ = obtener_claims(event)
    params = event.get('queryStringParameters') or {}

    consulta = {'KeyConditionExpression': Key('tenant_id').eq(tenant_id), 'Limit': leer_limite(params)}
    filtro = None
    if params.get('estado'):
        filtro = Attr('estado').eq(validar_estado_producto(params['estado']))
    if params.get('categoria'):
        condicion = Attr('categoria').eq(params['categoria'])
        filtro = condicion if filtro is None else filtro & condicion
    if filtro is not None:
        consulta['FilterExpression'] = filtro
    if params.get('siguiente'):
        consulta['ExclusiveStartKey'] = {'tenant_id': tenant_id, 'producto_id': params['siguiente']}

    resultado = tabla('TABLE_PRODUCTOS').query(**consulta)
    ultima = resultado.get('LastEvaluatedKey')
    return respuesta(200, {
        'productos': resultado.get('Items', []),
        'siguiente': ultima['producto_id'] if ultima else None
    })
