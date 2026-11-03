import os
import jwt

def lambda_handler(event, context):
    token = (event.get('headers') or {}).get('authorization', '')
    if token.startswith('Bearer '):
        token = token[7:]

    try:
        datos = jwt.decode(token, os.environ['JWT_SECRET'], algorithms=['HS256'])
        return {
            'isAuthorized': True,
            'context': {
                'tenant_id': datos['tenant_id'],
                'usuario_id': datos['usuario_id'],
                'rol': datos['rol']
            }
        }
    except Exception as e:
        print(f"Token rechazado: {e}")
        return {'isAuthorized': False}
