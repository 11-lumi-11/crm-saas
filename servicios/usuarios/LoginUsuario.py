import boto3
import os
import json
import hashlib
import hmac
import jwt
from datetime import datetime, timedelta, timezone
from boto3.dynamodb.conditions import Key

def respuesta(codigo_http, cuerpo):
    return {'statusCode': codigo_http, 'body': json.dumps(cuerpo)}

def lambda_handler(event, context):
    body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body') or {}
    correo = (body.get('correo') or '').strip().lower()
    contrasena = body.get('contrasena') or ''

    if not correo or not contrasena:
        return respuesta(400, {'codigo': 'datos_incompletos', 'mensaje': 'Correo y contraseña requeridos'})

    table = boto3.resource('dynamodb').Table(os.environ['TABLE_USUARIOS'])
    items = table.query(
        IndexName='correo-index',
        KeyConditionExpression=Key('correo').eq(correo),
        Limit=1
    ).get('Items', [])

    credenciales_invalidas = respuesta(401, {'codigo': 'no_autorizado', 'mensaje': 'Credenciales inválidas'})
    if not items:
        return credenciales_invalidas

    usuario = items[0]
    hash_ingresado = hashlib.sha256(contrasena.encode('utf-8')).hexdigest()
    if not hmac.compare_digest(usuario.get('contrasena_hash', ''), hash_ingresado):
        return credenciales_invalidas

    if usuario.get('estado') != 'activo':
        return respuesta(403, {'codigo': 'usuario_inactivo', 'mensaje': 'El usuario está inactivo'})

    horas = int(os.environ.get('JWT_EXPIRACION_HORAS', '8'))
    ahora = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            'usuario_id': usuario['usuario_id'],
            'tenant_id': usuario['tenant_id'],
            'rol': usuario['rol'],
            'iat': ahora,
            'exp': ahora + timedelta(hours=horas)
        },
        os.environ['JWT_SECRET'],
        algorithm='HS256'
    )

    return respuesta(200, {
        'token': token,
        'expira_en_segundos': horas * 3600,
        'tenant_id': usuario['tenant_id'],
        'usuario_id': usuario['usuario_id'],
        'rol': usuario['rol']
    })
