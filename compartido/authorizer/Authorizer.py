import os
import boto3
import jwt


def lambda_handler(event, context):
    token = (event.get('headers') or {}).get('authorization', '')
    if token.startswith('Bearer '):
        token = token[7:]
    try:
        datos = jwt.decode(token, os.environ['JWT_SECRET'], algorithms=['HS256'],
                           options={'require': ['exp', 'tenant_id', 'usuario_id', 'rol']})
        if not all(isinstance(datos[k], str) and datos[k] for k in ('tenant_id', 'usuario_id', 'rol')):
            return {'isAuthorized': False}
        db = boto3.resource('dynamodb')
        usuario = db.Table(os.environ['TABLE_USUARIOS']).get_item(
            Key={k: datos[k] for k in ('tenant_id', 'usuario_id')}, ConsistentRead=True).get('Item', {})
        tenant = db.Table(os.environ['TABLE_TENANTS']).get_item(
            Key={'tenant_id': datos['tenant_id']}, ConsistentRead=True).get('Item', {})
        if (usuario.get('estado') != 'activo' or tenant.get('estado') != 'activo'
                or usuario.get('rol') not in ('admin', 'gerente', 'vendedor')
                or usuario.get('rol') != datos['rol']):
            return {'isAuthorized': False}
        return {'isAuthorized': True, 'context': {k: datos[k] for k in ('tenant_id', 'usuario_id', 'rol')}}
    except Exception:
        # Ante errores de token o de la base de identidad se rechaza el acceso.
        print('Acceso rechazado por el Authorizer')
        return {'isAuthorized': False}
