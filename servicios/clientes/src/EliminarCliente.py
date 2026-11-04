import boto3
import os
import json
from boto3.dynamodb.conditions import Key

def respuesta(codigo_http, cuerpo):
    return {'statusCode': codigo_http, 'body': json.dumps(cuerpo)}

def lambda_handler(event, context):
    claims = event.get('requestContext', {}).get('authorizer', {}).get('lambda', {})
    tenant_id = claims.get('tenant_id')
    rol = claims.get('rol')
    cliente_id = (event.get('pathParameters') or {}).get('cliente_id')

    if rol not in ('gerente', 'admin'):
        return respuesta(403, {'codigo': 'prohibido', 'mensaje': 'Solo un gerente o admin puede eliminar clientes'})

    dynamodb = boto3.resource('dynamodb')
    tabla_clientes = dynamodb.Table(os.environ['TABLE_CLIENTES'])
    tabla_contactos = dynamodb.Table(os.environ['TABLE_CONTACTOS'])

    actual = tabla_clientes.get_item(Key={'tenant_id': tenant_id, 'cliente_id': cliente_id}).get('Item')
    if not actual:
        return respuesta(404, {'codigo': 'no_encontrado', 'mensaje': 'El cliente no existe'})

    consulta = {
        'IndexName': os.environ.get('INDEX_CLIENTE', 'cliente_id-index'),
        'KeyConditionExpression': Key('tenant_id').eq(tenant_id) & Key('cliente_id').eq(cliente_id)
    }
    while True:
        respuesta_contactos = tabla_contactos.query(**consulta)
        for contacto in respuesta_contactos.get('Items', []):
            tabla_contactos.delete_item(Key={
                'tenant_id': tenant_id,
                'contacto_id': contacto['contacto_id']
            })
        if not respuesta_contactos.get('LastEvaluatedKey'):
            break
        consulta['ExclusiveStartKey'] = respuesta_contactos['LastEvaluatedKey']

    tabla_clientes.delete_item(Key={'tenant_id': tenant_id, 'cliente_id': cliente_id})

    return respuesta(200, {'mensaje': 'Cliente eliminado correctamente', 'cliente_id': cliente_id})
