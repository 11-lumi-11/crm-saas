import os
import boto3
import jwt
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from datetime import datetime, timedelta, timezone
from crm_comun import ErrorNegocio, leer_body, manejar_errores, respuesta, validar_correo, validar_texto
from crm_comun.contrasenas import crear_hash, verificar


@manejar_errores
def lambda_handler(event, context):
    body = leer_body(event)
    correo = validar_correo(body.get('correo'))
    contrasena = body.get('contrasena')
    validar_texto(contrasena, 'contrasena')
    tabla = boto3.resource('dynamodb').Table(os.environ['TABLE_USUARIOS'])
    candidatos = tabla.query(IndexName='correo-index',
                              KeyConditionExpression=Key('correo').eq(correo), Limit=2).get('Items', [])
    if len(candidatos) != 1:
        raise ErrorNegocio(401, 'no_autorizado', 'Credenciales inválidas')
    clave = {k: candidatos[0][k] for k in ('tenant_id', 'usuario_id')}
    usuario = tabla.get_item(Key=clave, ConsistentRead=True).get('Item', {})
    if not verificar(contrasena, usuario.get('contrasena_hash')):
        raise ErrorNegocio(401, 'no_autorizado', 'Credenciales inválidas')
    if usuario.get('estado') != 'activo':
        raise ErrorNegocio(403, 'usuario_inactivo', 'El usuario está inactivo')
    tenant = boto3.resource('dynamodb').Table(os.environ['TABLE_TENANTS']).get_item(
        Key={'tenant_id': usuario['tenant_id']}, ConsistentRead=True).get('Item', {})
    if tenant.get('estado') != 'activo':
        raise ErrorNegocio(403, 'tenant_inactivo', 'La empresa está suspendida')
    if not usuario['contrasena_hash'].startswith('pbkdf2_sha256$'):
        try:
            tabla.update_item(Key=clave, UpdateExpression='SET contrasena_hash = :nuevo',
                              ConditionExpression='contrasena_hash = :anterior',
                              ExpressionAttributeValues={':nuevo': crear_hash(contrasena),
                                                         ':anterior': usuario['contrasena_hash']})
        except ClientError as error:
            if error.response['Error']['Code'] != 'ConditionalCheckFailedException':
                raise
    horas = int(os.environ.get('JWT_EXPIRACION_HORAS', '1'))
    ahora = datetime.now(timezone.utc)
    token = jwt.encode({**{k: usuario[k] for k in ('usuario_id', 'tenant_id', 'rol')},
                        'iat': ahora, 'exp': ahora + timedelta(hours=horas)},
                       os.environ['JWT_SECRET'], algorithm='HS256')
    return respuesta(200, {'token': token, 'expira_en_segundos': horas * 3600,
                           **{k: usuario[k] for k in ('usuario_id', 'tenant_id', 'rol')}})
