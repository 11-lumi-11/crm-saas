import os
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from src.utilidades import (
    ErrorNegocio, manejar_errores, respuesta, obtener_claims, tabla, leer_limite, ESTADOS_COTIZACION
)

# filtro de query string -> variable de entorno con el nombre del GSI
FILTROS = {'oportunidad_id': 'INDEX_OPORTUNIDAD', 'estado': 'INDEX_ESTADO'}


@manejar_errores
def lambda_handler(event, context):
    tenant_id, _, _ = obtener_claims(event)
    params = event.get('queryStringParameters') or {}

    filtros = {campo: params[campo] for campo in FILTROS if params.get(campo)}
    if len(filtros) > 1:
        raise ErrorNegocio(400, 'filtros_incompatibles', 'Use solo un filtro: oportunidad_id o estado')
    if filtros.get('estado') is not None and filtros['estado'] not in ESTADOS_COTIZACION:
        raise ErrorNegocio(400, 'estado_invalido', 'Estado no permitido')

    consulta = {'Limit': leer_limite(params), 'FilterExpression': Attr('fecha_eliminacion').not_exists()}
    if filtros:
        campo, valor = next(iter(filtros.items()))
        consulta['IndexName'] = os.environ[FILTROS[campo]]
        consulta['KeyConditionExpression'] = Key('tenant_id').eq(tenant_id) & Key(campo).eq(valor)
        if params.get('siguiente'):
            consulta['ExclusiveStartKey'] = {'tenant_id': tenant_id, 'cotizacion_id': params['siguiente'], campo: valor}
    else:
        consulta['KeyConditionExpression'] = Key('tenant_id').eq(tenant_id)
        if params.get('siguiente'):
            consulta['ExclusiveStartKey'] = {'tenant_id': tenant_id, 'cotizacion_id': params['siguiente']}

    try:
        resultado = tabla('TABLE_COTIZACIONES').query(**consulta)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException':
            raise ErrorNegocio(400, 'paginacion_invalida', 'El valor de siguiente no corresponde a esta consulta')
        raise

    ultima = resultado.get('LastEvaluatedKey')
    return respuesta(200, {
        'cotizaciones': resultado.get('Items', []),
        'siguiente': ultima['cotizacion_id'] if ultima else None
    })
