import os
import boto3
from botocore.exceptions import ClientError
from crm_comun import ErrorNegocio, ahora, claims, manejar_errores, respuesta


@manejar_errores
def lambda_handler(event, context):
    identidad = claims(event)
    if identidad['rol'] not in ('admin', 'gerente'):
        raise ErrorNegocio(403, 'prohibido', 'Solo gerente o admin puede eliminar clientes')
    cliente_id = (event.get('pathParameters') or {}).get('cliente_id')
    try:
        boto3.resource('dynamodb').Table(os.environ['TABLE_CLIENTES']).update_item(
            Key={'tenant_id': identidad['tenant_id'], 'cliente_id': cliente_id},
            UpdateExpression='SET eliminado = :si, fecha_eliminacion = :fecha, fecha_actualizacion = :fecha, #estado = :inactivo',
            ConditionExpression='attribute_exists(cliente_id) AND attribute_not_exists(fecha_eliminacion)',
            ExpressionAttributeNames={'#estado': 'estado'},
            ExpressionAttributeValues={':si': True, ':fecha': ahora(), ':inactivo': 'inactivo'})
    except ClientError as error:
        if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise ErrorNegocio(404, 'no_encontrado', 'El cliente no existe')
        raise
    return respuesta(200, {'mensaje': 'Cliente archivado correctamente', 'cliente_id': cliente_id})
