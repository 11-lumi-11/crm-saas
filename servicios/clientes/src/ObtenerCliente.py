from crm_comun import respuesta, claims, manejar_errores
import boto3
import os

@manejar_errores
def lambda_handler(event, context):
    identidad = claims(event)
    tenant_id = identidad.get('tenant_id')
    cliente_id = (event.get('pathParameters') or {}).get('cliente_id')

    table = boto3.resource('dynamodb').Table(os.environ['TABLE_CLIENTES'])
    item = table.get_item(Key={'tenant_id': tenant_id, 'cliente_id': cliente_id}).get('Item')

    if not item or item.get('eliminado'):
        return respuesta(404, {'codigo': 'no_encontrado', 'mensaje': 'El cliente no existe'})

    return respuesta(200, {'cliente': item})
