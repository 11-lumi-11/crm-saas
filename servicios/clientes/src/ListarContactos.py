import boto3
import os
import json
from boto3.dynamodb.conditions import Key

def respuesta(codigo_http, cuerpo):
    return {'statusCode': codigo_http, 'body': json.dumps(cuerpo, default=str)}

def lambda_handler(event, context):
    claims = event.get('requestContext', {}).get('authorizer', {}).get('lambda', {})
    tenant_id = claims.get('tenant_id')
    cliente_id = (event.get('pathParameters') or {}).get('cliente_id')

    dynamodb = boto3.resource('dynamodb')
    cliente = dynamodb.Table(os.environ['TABLE_CLIENTES']).get_item(
        Key={'tenant_id': tenant_id, 'cliente_id': cliente_id}
    ).get('Item')
    if not cliente:
        return respuesta(404, {'codigo': 'no_encontrado', 'mensaje': 'El cliente no existe'})

    params = event.get('queryStringParameters') or {}
    try:
        limite = min(max(int(params.get('limite', 50)), 1), 100)
    except ValueError:
        limite = 50

    consulta = {
        'IndexName': os.environ.get('INDEX_CLIENTE', 'cliente_id-index'),
        'KeyConditionExpression': Key('tenant_id').eq(tenant_id) & Key('cliente_id').eq(cliente_id),
        'Limit': limite
    }
    if params.get('siguiente'):
        consulta['ExclusiveStartKey'] = {
            'tenant_id': tenant_id,
            'contacto_id': params['siguiente'],
            'cliente_id': cliente_id
        }

    response = dynamodb.Table(os.environ['TABLE_CONTACTOS']).query(**consulta)
    ultima = response.get('LastEvaluatedKey')
    return respuesta(200, {
        'contactos': response.get('Items', []),
        'siguiente': ultima['contacto_id'] if ultima else None
    })
