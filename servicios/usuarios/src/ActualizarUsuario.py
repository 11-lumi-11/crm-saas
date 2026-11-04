import boto3
import os
import json

ROLES = ('admin', 'gerente', 'vendedor')
ESTADOS = ('activo', 'inactivo')

def respuesta(codigo_http, cuerpo):
    return {'statusCode': codigo_http, 'body': json.dumps(cuerpo, default=str)}

def lambda_handler(event, context):
    claims = event.get('requestContext', {}).get('authorizer', {}).get('lambda', {})
    tenant_id = claims.get('tenant_id')

    if claims.get('rol') != 'admin':
        return respuesta(403, {'codigo': 'prohibido', 'mensaje': 'Solo administradores pueden modificar usuarios'})

    usuario_id = (event.get('pathParameters') or {}).get('usuario_id')
    body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body') or {}

    cambios, valores = [], {}
    if body.get('rol') is not None:
        if body['rol'] not in ROLES:
            return respuesta(400, {'codigo': 'rol_invalido', 'mensaje': 'Rol no permitido'})
        cambios.append('rol = :rol')
        valores[':rol'] = body['rol']
    if body.get('estado') is not None:
        if body['estado'] not in ESTADOS:
            return respuesta(400, {'codigo': 'estado_invalido', 'mensaje': 'Estado no permitido'})
        cambios.append('estado = :estado')
        valores[':estado'] = body['estado']

    if not cambios:
        return respuesta(400, {'codigo': 'datos_incompletos', 'mensaje': 'Indique rol y/o estado'})

    table = boto3.resource('dynamodb').Table(os.environ['TABLE_USUARIOS'])
    try:
        response = table.update_item(
            Key={'tenant_id': tenant_id, 'usuario_id': usuario_id},
            UpdateExpression='SET ' + ', '.join(cambios),
            ExpressionAttributeValues=valores,
            ConditionExpression='attribute_exists(usuario_id)',
            ReturnValues='ALL_NEW'
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return respuesta(404, {'codigo': 'no_encontrado', 'mensaje': 'El usuario no existe'})

    usuario = response['Attributes']
    usuario.pop('contrasena_hash', None)
    return respuesta(200, {'mensaje': 'Usuario actualizado correctamente', 'usuario': usuario})
