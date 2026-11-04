import boto3
import os
import json
from boto3.dynamodb.conditions import Key

def lambda_handler(event, context):
    claims = event.get('requestContext', {}).get('authorizer', {}).get('lambda', {})
    tenant_id = claims.get('tenant_id')

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
        consulta['ExclusiveStartKey'] = {'tenant_id': tenant_id, 'cliente_id': params['siguiente']}

    table = boto3.resource('dynamodb').Table(os.environ['TABLE_CLIENTES'])
    response = table.query(**consulta)

    ultima = response.get('LastEvaluatedKey')
    return {
        'statusCode': 200,
        'body': json.dumps({
            'clientes': response.get('Items', []),
            'siguiente': ultima['cliente_id'] if ultima else None
        }, default=str)
    }
