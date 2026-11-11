import os
from boto3.dynamodb.conditions import Key

from crm_comun import ErrorNegocio, manejar_errores, respuesta, obtener_claims
from src.utilidades import dynamodb, tabla, destinos_de, id_lectura

# Campos internos que no se devuelven al cliente
INTERNOS = ('destino', 'orden')


def leidas_por(tenant_id, usuario_id, notificaciones):
    # Busca en t_lecturas_notificaciones cuáles de estos avisos leyó el usuario
    if not notificaciones:
        return set()
    nombre = os.environ['TABLE_LECTURAS']
    pendientes = {nombre: {'Keys': [
        {'tenant_id': tenant_id, 'lectura_id': id_lectura(n['notificacion_id'], usuario_id)}
        for n in notificaciones]}}
    leidas = set()
    while pendientes:
        resultado = dynamodb.batch_get_item(RequestItems=pendientes)
        for item in resultado.get('Responses', {}).get(nombre, []):
            leidas.add(item['notificacion_id'])
        pendientes = resultado.get('UnprocessedKeys') or None
    return leidas


@manejar_errores
def lambda_handler(event, context):
    tenant_id, usuario_id, rol = obtener_claims(event)

    params = event.get('queryStringParameters') or {}
    try:
        limite = min(max(int(params.get('limite', 50)), 1), 100)
    except ValueError:
        raise ErrorNegocio(400, 'datos_invalidos', 'limite debe ser un número entre 1 y 100')
    solo_no_leidas = params.get('solo_no_leidas') == 'true'
    siguiente = params.get('siguiente')

    # Dos consultas al GSI: avisos para el usuario y avisos para su rol (más recientes primero)
    encontrados, hay_mas = [], False
    for destino in destinos_de(tenant_id, usuario_id, rol):
        condicion = Key('destino').eq(destino)
        if siguiente:
            condicion = condicion & Key('orden').lt(siguiente)
        resultado = tabla('TABLE_NOTIFICACIONES').query(
            IndexName=os.environ['INDEX_DESTINO'], KeyConditionExpression=condicion,
            ScanIndexForward=False, Limit=limite)
        encontrados.extend(resultado.get('Items', []))
        hay_mas = hay_mas or bool(resultado.get('LastEvaluatedKey'))

    encontrados.sort(key=lambda n: n['orden'], reverse=True)
    hay_mas = hay_mas or len(encontrados) > limite
    pagina = encontrados[:limite]

    leidas = leidas_por(tenant_id, usuario_id, pagina)
    for n in pagina:
        n['leida'] = n['notificacion_id'] in leidas
    cursor = pagina[-1]['orden'] if (pagina and hay_mas) else None

    if solo_no_leidas:
        pagina = [n for n in pagina if not n['leida']]
    for n in pagina:
        for campo in INTERNOS:
            n.pop(campo, None)

    return respuesta(200, {
        'notificaciones': pagina,
        'no_leidas_en_pagina': sum(1 for n in pagina if not n['leida']),
        'siguiente': cursor
    })
