import boto3
import os
import json
from datetime import datetime, timezone

TIPOS = ('empresa', 'persona')
ESTADOS = ('prospecto', 'activo', 'inactivo')
CAMPOS = ('nombre', 'tipo', 'documento', 'correo', 'telefono', 'industria', 'ciudad', 'estado', 'responsable_id')

def respuesta(codigo_http, cuerpo):
    return {'statusCode': codigo_http, 'body': json.dumps(cuerpo, default=str)}

def lambda_handler(event, context):
    claims = event.get('requestContext', {}).get('authorizer', {}).get('lambda', {})
    tenant_id = claims.get('tenant_id')
    rol = claims.get('rol')
    cliente_id = (event.get('pathParameters') or {}).get('cliente_id')
    body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body') or {}

    table = boto3.resource('dynamodb').Table(os.environ['TABLE_CLIENTES'])
    actual = table.get_item(Key={'tenant_id': tenant_id, 'cliente_id': cliente_id}).get('Item')
    if not actual:
        return respuesta(404, {'codigo': 'no_encontrado', 'mensaje': 'El cliente no existe'})

    if 'responsable_id' in body and body['responsable_id'] != actual.get('responsable_id') and rol == 'vendedor':
        return respuesta(403, {'codigo': 'prohibido', 'mensaje': 'Un vendedor no puede reasignar el responsable'})

    if body.get('tipo') is not None and body['tipo'] not in TIPOS:
        return respuesta(400, {'codigo': 'tipo_invalido', 'mensaje': 'Tipo no permitido'})

    if body.get('estado') is not None and body['estado'] not in ESTADOS:
        return respuesta(400, {'codigo': 'estado_invalido', 'mensaje': 'Estado no permitido'})

    cambios, valores, nombres = [], {}, {}
    for campo in CAMPOS:
        if campo not in body or body[campo] is None:
            continue
        valor = body[campo]
        if campo == 'correo':
            valor = str(valor).strip().lower()
        alias = f'#c_{campo}'
        cambios.append(f'{alias} = :{campo}')
        valores[f':{campo}'] = valor
        nombres[alias] = campo

    if not cambios:
        return respuesta(400, {'codigo': 'datos_incompletos', 'mensaje': 'Indique al menos un campo para actualizar'})

    cambios.append('fecha_actualizacion = :fecha')
    valores[':fecha'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    response = table.update_item(
        Key={'tenant_id': tenant_id, 'cliente_id': cliente_id},
        UpdateExpression='SET ' + ', '.join(cambios),
        ExpressionAttributeValues=valores,
        ExpressionAttributeNames=nombres,
        ConditionExpression='attribute_exists(cliente_id)',
        ReturnValues='ALL_NEW'
    )

    return respuesta(200, {
        'mensaje': 'Cliente actualizado correctamente',
        'cliente': response['Attributes']
    })
