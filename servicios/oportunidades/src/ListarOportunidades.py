import os
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from src.utilidades import (
    ErrorNegocio, manejar_errores, respuesta, obtener_claims, tabla, ETAPAS
)

# filtro de query string -> variable de entorno con el nombre del GSI
FILTROS = {
    'cliente_id': 'INDEX_CLIENTE',
    'responsable_id': 'INDEX_RESPONSABLE',
    'etapa': 'INDEX_ETAPA'
}


@manejar_errores
def lambda_handler(event, context):
    tenant_id, _, _ = obtener_claims(event)

    params = event.get('queryStringParameters') or {}
    try:
        limite = min(max(int(params.get('limite', 50)), 1), 100)
    except ValueError:
        limite = 50

    filtros = {campo: params[campo] for campo in FILTROS if params.get(campo)}
    if len(filtros) > 1:
        raise ErrorNegocio(400, 'filtros_incompatibles', 'Use solo un filtro: cliente_id, responsable_id o etapa')
    if filtros.get('etapa') is not None and filtros['etapa'] not in ETAPAS:
        raise ErrorNegocio(400, 'etapa_invalida', 'Etapa no permitida')

    consulta = {'Limit': limite, 'FilterExpression': Attr('fecha_eliminacion').not_exists()}
    if filtros:
        campo, valor = next(iter(filtros.items()))
        consulta['IndexName'] = os.environ[FILTROS[campo]]
        consulta['KeyConditionExpression'] = Key('tenant_id').eq(tenant_id) & Key(campo).eq(valor)
        if params.get('siguiente'):
            consulta['ExclusiveStartKey'] = {
                'tenant_id': tenant_id,
                'oportunidad_id': params['siguiente'],
                campo: valor
            }
    else:
        consulta['KeyConditionExpression'] = Key('tenant_id').eq(tenant_id)
        if params.get('siguiente'):
            consulta['ExclusiveStartKey'] = {'tenant_id': tenant_id, 'oportunidad_id': params['siguiente']}

    try:
        resultado = tabla('TABLE_OPORTUNIDADES').query(**consulta)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException':
            raise ErrorNegocio(400, 'paginacion_invalida', 'El valor de siguiente no corresponde a esta consulta')
        raise

    ultima = resultado.get('LastEvaluatedKey')
    return respuesta(200, {
        'oportunidades': resultado.get('Items', []),
        'siguiente': ultima['oportunidad_id'] if ultima else None
    })
