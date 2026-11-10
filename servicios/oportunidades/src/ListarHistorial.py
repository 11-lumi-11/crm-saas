import os
from boto3.dynamodb.conditions import Key

from src.utilidades import manejar_errores, respuesta, obtener_claims, tabla, leer_oportunidad


@manejar_errores
def lambda_handler(event, context):
    tenant_id, _, _ = obtener_claims(event)
    oportunidad_id = (event.get('pathParameters') or {}).get('oportunidad_id')

    leer_oportunidad(tenant_id, oportunidad_id)  # 404 si no existe en el tenant

    consulta = {
        'IndexName': os.environ.get('INDEX_HISTORIAL', 'oportunidad_id-index'),
        'KeyConditionExpression': Key('tenant_id').eq(tenant_id) & Key('oportunidad_id').eq(oportunidad_id)
    }
    tabla_historial = tabla('TABLE_HISTORIAL')
    items = []
    while True:
        resultado = tabla_historial.query(**consulta)
        items.extend(resultado.get('Items', []))
        if not resultado.get('LastEvaluatedKey'):
            break
        consulta['ExclusiveStartKey'] = resultado['LastEvaluatedKey']

    items.sort(key=lambda h: h['fecha_cambio'])
    return respuesta(200, {'historial': items})
