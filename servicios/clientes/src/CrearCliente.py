import boto3
import uuid
import os
import json
from datetime import datetime, timezone

TIPOS = ('empresa', 'persona')
ESTADOS = ('prospecto', 'activo', 'inactivo')

def respuesta(codigo_http, cuerpo):
    return {'statusCode': codigo_http, 'body': json.dumps(cuerpo)}

def lambda_handler(event, context):
    claims = event.get('requestContext', {}).get('authorizer', {}).get('lambda', {})
    tenant_id = claims.get('tenant_id')
    usuario_id = claims.get('usuario_id')
    rol = claims.get('rol')

    body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body') or {}
    nombre = body.get('nombre')
    tipo = body.get('tipo')
    estado = body.get('estado', 'prospecto')
    responsable_id = body.get('responsable_id') or usuario_id

    if not tenant_id or not nombre or not tipo:
        return respuesta(400, {'codigo': 'datos_incompletos', 'mensaje': 'Faltan campos obligatorios'})

    if tipo not in TIPOS:
        return respuesta(400, {'codigo': 'tipo_invalido', 'mensaje': 'Tipo no permitido'})

    if estado not in ESTADOS:
        return respuesta(400, {'codigo': 'estado_invalido', 'mensaje': 'Estado no permitido'})

    if responsable_id != usuario_id and rol == 'vendedor':
        return respuesta(403, {'codigo': 'prohibido', 'mensaje': 'Un vendedor no puede asignar otro responsable'})

    fecha = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    cliente_id = f"cli_{str(uuid.uuid4()).replace('-', '')[:8]}"
    sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')

    item = {
        'tenant_id': tenant_id,
        'cliente_id': cliente_id,
        'nombre': nombre,
        'tipo': tipo,
        'documento': body.get('documento', ''),
        'correo': (body.get('correo') or '').strip().lower(),
        'telefono': body.get('telefono', ''),
        'industria': body.get('industria', ''),
        'ciudad': body.get('ciudad', ''),
        'estado': estado,
        'responsable_id': responsable_id,
        'fecha_creacion': fecha,
        'fecha_actualizacion': fecha
    }

    table = boto3.resource('dynamodb').Table(os.environ['TABLE_CLIENTES'])
    table.put_item(Item=item)

    if sns_topic_arn:
        try:
            evento = {
                'evento_id': f"evt_{str(uuid.uuid4())[:8]}",
                'tipo': 'cliente.creado',
                'tenant_id': tenant_id,
                'fecha': fecha,
                'datos': {
                    'cliente_id': cliente_id,
                    'nombre': nombre,
                    'responsable_id': responsable_id
                }
            }
            boto3.client('sns').publish(
                TopicArn=sns_topic_arn,
                Message=json.dumps(evento),
                MessageAttributes={'tipo': {'DataType': 'String', 'StringValue': 'cliente.creado'}}
            )
        except Exception as e_sns:
            print(f"Advertencia: No se pudo publicar en SNS: {e_sns}")

    return respuesta(201, {
        'mensaje': 'Cliente creado exitosamente',
        'cliente_id': cliente_id
    })
