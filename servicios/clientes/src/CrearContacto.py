import boto3
import uuid
import os
import json
from datetime import datetime, timezone

def respuesta(codigo_http, cuerpo):
    return {'statusCode': codigo_http, 'body': json.dumps(cuerpo)}

def lambda_handler(event, context):
    claims = event.get('requestContext', {}).get('authorizer', {}).get('lambda', {})
    tenant_id = claims.get('tenant_id')
    cliente_id = (event.get('pathParameters') or {}).get('cliente_id')
    body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body') or {}
    nombre = body.get('nombre')

    if not tenant_id or not cliente_id or not nombre:
        return respuesta(400, {'codigo': 'datos_incompletos', 'mensaje': 'Faltan campos obligatorios'})

    dynamodb = boto3.resource('dynamodb')
    tabla_clientes = dynamodb.Table(os.environ['TABLE_CLIENTES'])
    cliente = tabla_clientes.get_item(Key={'tenant_id': tenant_id, 'cliente_id': cliente_id}).get('Item')
    if not cliente:
        return respuesta(404, {'codigo': 'no_encontrado', 'mensaje': 'El cliente no existe'})

    fecha = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    contacto_id = f"con_{str(uuid.uuid4()).replace('-', '')[:8]}"
    es_principal = bool(body.get('es_principal', False))

    item = {
        'tenant_id': tenant_id,
        'contacto_id': contacto_id,
        'cliente_id': cliente_id,
        'nombre': nombre,
        'cargo': body.get('cargo', ''),
        'correo': (body.get('correo') or '').strip().lower(),
        'telefono': body.get('telefono', ''),
        'es_principal': es_principal,
        'fecha_creacion': fecha
    }

    tabla_contactos = dynamodb.Table(os.environ['TABLE_CONTACTOS'])
    tabla_contactos.put_item(Item=item)

    return respuesta(201, {
        'mensaje': 'Contacto creado exitosamente',
        'contacto_id': contacto_id
    })
