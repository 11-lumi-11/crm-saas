import boto3
import os
import json

def respuesta(codigo_http, cuerpo):
    return {'statusCode': codigo_http, 'body': json.dumps(cuerpo, default=str)}

def lambda_handler(event, context):
    claims = event.get('requestContext', {}).get('authorizer', {}).get('lambda', {})
    tenant_id = claims.get('tenant_id')
    cliente_id = (event.get('pathParameters') or {}).get('cliente_id')

    table = boto3.resource('dynamodb').Table(os.environ['TABLE_CLIENTES'])
    item = table.get_item(Key={'tenant_id': tenant_id, 'cliente_id': cliente_id}).get('Item')

    if not item:
        return respuesta(404, {'codigo': 'no_encontrado', 'mensaje': 'El cliente no existe'})

    return respuesta(200, {'cliente': item})
