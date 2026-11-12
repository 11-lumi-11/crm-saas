import os
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from crm_comun import ErrorNegocio
from src.utilidades import (endpoint, obtener_claims, tabla, ESTADOS, tipo_valido, fecha_utc,
    validar_id, validar_responsable, cursor_codificar, cursor_leer, publica, respuesta)

FILTROS = {'responsable_id': 'INDEX_RESPONSABLE', 'estado': 'INDEX_ESTADO',
           'oportunidad_id': 'INDEX_OPORTUNIDAD'}


@endpoint
def lambda_handler(event, context):
    tenant_id, _, _ = obtener_claims(event)
    params = event.get('queryStringParameters') or {}
    if set(params) - {*FILTROS, 'tipo', 'desde', 'hasta', 'limite', 'siguiente'}:
        raise ErrorNegocio(400, 'datos_invalidos', 'Filtro desconocido')
    try:
        limite = int(params.get('limite', 50))
        if not 1 <= limite <= 100:
            raise ValueError()
    except (TypeError, ValueError):
        raise ErrorNegocio(400, 'datos_invalidos', 'limite debe ser un entero de 1 a 100')
    consulta = {'tenant_id': tenant_id}
    for campo in (*FILTROS, 'tipo', 'desde', 'hasta'):
        if campo not in params:
            continue
        valor = params[campo]
        if campo == 'responsable_id':
            valor = validar_responsable(valor)
        elif campo == 'oportunidad_id':
            valor = validar_id(valor, campo, 'opo')
        elif campo == 'estado':
            if valor not in ESTADOS:
                raise ErrorNegocio(400, 'estado_invalido', 'Estado no permitido')
        elif campo == 'tipo':
            valor = tipo_valido(valor)
        else:
            valor = fecha_utc(valor, campo)
        consulta[campo] = valor
    if consulta.get('desde', '') > consulta.get('hasta', '9999'):
        raise ErrorNegocio(400, 'datos_invalidos', 'desde debe ser anterior o igual a hasta')
    # Las fechas usan el índice cronológico. Sin rango se prioriza un filtro de igualdad.
    indice = ('fecha_programada' if ('desde' in consulta or 'hasta' in consulta) else
              next((c for c in FILTROS if c in consulta), 'fecha_programada'))
    condicion = Key('tenant_id').eq(tenant_id)
    if indice == 'fecha_programada':
        if 'desde' in consulta and 'hasta' in consulta:
            condicion &= Key(indice).between(consulta['desde'], consulta['hasta'])
        elif 'desde' in consulta:
            condicion &= Key(indice).gte(consulta['desde'])
        elif 'hasta' in consulta:
            condicion &= Key(indice).lte(consulta['hasta'])
        nombre_indice = os.environ['INDEX_FECHA']
    else:
        condicion &= Key(indice).eq(consulta[indice])
        nombre_indice = os.environ[FILTROS[indice]]
    argumentos = dict(IndexName=nombre_indice, KeyConditionExpression=condicion, Limit=limite)
    filtro = None
    for campo in (*FILTROS, 'tipo'):
        if campo in consulta and campo != indice:
            nuevo = Attr(campo).eq(consulta[campo])
            filtro = nuevo if filtro is None else filtro & nuevo
    if filtro is not None:
        argumentos['FilterExpression'] = filtro
    if params.get('siguiente'):
        argumentos['ExclusiveStartKey'] = cursor_leer(params['siguiente'], consulta, indice)
    try:
        resultado = tabla().query(**argumentos)
    except ClientError as error:
        if error.response['Error']['Code'] == 'ValidationException':
            raise ErrorNegocio(400, 'paginacion_invalida', 'La consulta o el cursor son inválidos')
        raise
    ultima = resultado.get('LastEvaluatedKey')
    return respuesta(200, {'actividades': [publica(i) for i in resultado.get('Items', [])],
        'siguiente': cursor_codificar(ultima, consulta) if ultima else None})
