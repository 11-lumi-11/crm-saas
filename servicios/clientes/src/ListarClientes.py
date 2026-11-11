from crm_comun import respuesta, claims, manejar_errores, validar_responsable
import boto3
import os
from boto3.dynamodb.conditions import Key, Attr

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
        'FilterExpression': Attr('fecha_eliminacion').not_exists(),
        'Limit': limite
    }
    if params.get('responsable_id'):
        responsable = validar_responsable(params['responsable_id'])
        consulta['IndexName'] = 'responsable_id-index'
        consulta['KeyConditionExpression'] &= Key('responsable_id').eq(responsable)
    if params.get('siguiente'):
        consulta['ExclusiveStartKey'] = {'tenant_id': tenant_id, 'cliente_id': params['siguiente']}

    if params.get('siguiente') and params.get('responsable_id'):
        consulta['ExclusiveStartKey']['responsable_id'] = responsable

    table = boto3.resource('dynamodb').Table(os.environ['TABLE_CLIENTES'])
    response = table.query(**consulta)

    ultima = response.get('LastEvaluatedKey')
    return respuesta(200, {'clientes': response.get('Items', []), 'siguiente': ultima['cliente_id'] if ultima else None})
