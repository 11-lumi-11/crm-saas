from botocore.exceptions import ClientError
from src.utilidades import ErrorNegocio, manejar_errores, respuesta, obtener_claims, tabla, ahora


@manejar_errores
def lambda_handler(event, context):
    tenant_id, _, rol = obtener_claims(event)
    if rol not in ('gerente', 'admin'):
        raise ErrorNegocio(403, 'prohibido', 'Solo gerente o admin puede eliminar oportunidades')
    oportunidad_id = (event.get('pathParameters') or {}).get('oportunidad_id')
    try:
        tabla('TABLE_OPORTUNIDADES').update_item(
            Key={'tenant_id': tenant_id, 'oportunidad_id': oportunidad_id},
            UpdateExpression='SET eliminado = :si, fecha_eliminacion = :fecha, fecha_actualizacion = :fecha',
            ConditionExpression='attribute_exists(oportunidad_id) AND attribute_not_exists(fecha_eliminacion)',
            ExpressionAttributeValues={':si': True, ':fecha': ahora()})
    except ClientError as error:
        if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise ErrorNegocio(404, 'no_encontrado', 'La oportunidad no existe')
        raise
    return respuesta(200, {'mensaje': 'Oportunidad archivada correctamente', 'oportunidad_id': oportunidad_id})
