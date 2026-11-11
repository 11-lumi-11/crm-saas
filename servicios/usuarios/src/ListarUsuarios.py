from crm_comun import respuesta, claims, manejar_errores
import boto3
import os
from boto3.dynamodb.conditions import Key

@manejar_errores
def lambda_handler(event, context):
    identidad = claims(event)
    tenant_id = identidad.get('tenant_id')

    params = event.get('queryStringParameters') or {}
    try:
        limite = min(max(int(params.get('limite', 50)), 1), 100)
    except ValueError:
        limite = 50

    consulta = {
        'KeyConditionExpression': Key('tenant_id').eq(tenant_id),
        'Limit': limite
    }
    if params.get('siguiente'):
        consulta['ExclusiveStartKey'] = {'tenant_id': tenant_id, 'usuario_id': params['siguiente']}

    table = boto3.resource('dynamodb').Table(os.environ['TABLE_USUARIOS'])
    response = table.query(**consulta)

    usuarios = response.get('Items', [])
    for u in usuarios:
        u.pop('contrasena_hash', None)

    ultima = response.get('LastEvaluatedKey')
    return respuesta(200, {'usuarios': usuarios, 'siguiente': ultima['usuario_id'] if ultima else None})
