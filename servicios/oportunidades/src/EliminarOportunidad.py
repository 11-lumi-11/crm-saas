import os
from boto3.dynamodb.conditions import Key

from src.utilidades import ErrorNegocio, manejar_errores, respuesta, obtener_claims, tabla, leer_oportunidad


@manejar_errores
def lambda_handler(event, context):
    tenant_id, _, rol = obtener_claims(event)
    oportunidad_id = (event.get('pathParameters') or {}).get('oportunidad_id')

    if rol not in ('gerente', 'admin'):
        raise ErrorNegocio(403, 'prohibido', 'Solo un gerente o admin puede eliminar oportunidades')

    leer_oportunidad(tenant_id, oportunidad_id)

    tabla_historial = tabla('TABLE_HISTORIAL')
    consulta = {
        'IndexName': os.environ.get('INDEX_HISTORIAL', 'oportunidad_id-index'),
        'KeyConditionExpression': Key('tenant_id').eq(tenant_id) & Key('oportunidad_id').eq(oportunidad_id)
    }
    claves = []
    while True:
        resultado = tabla_historial.query(**consulta)
        claves.extend(h['historial_id'] for h in resultado.get('Items', []))
        if not resultado.get('LastEvaluatedKey'):
            break
        consulta['ExclusiveStartKey'] = resultado['LastEvaluatedKey']

    with tabla_historial.batch_writer() as lote:
        for historial_id in claves:
            lote.delete_item(Key={'tenant_id': tenant_id, 'historial_id': historial_id})

    tabla('TABLE_OPORTUNIDADES').delete_item(Key={'tenant_id': tenant_id, 'oportunidad_id': oportunidad_id})

    return respuesta(200, {'mensaje': 'Oportunidad eliminada correctamente', 'oportunidad_id': oportunidad_id})
