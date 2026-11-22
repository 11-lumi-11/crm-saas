"""Documentos privados de clientes. El tenant siempre procede del authorizer."""
import base64
import binascii
import os
from urllib.parse import quote

import boto3
from boto3.dynamodb.conditions import Key
from crm_comun import ErrorNegocio, ahora, claims, generar_id, leer_body, manejar_errores, respuesta

MAX_BYTES = 4 * 1024 * 1024


def contexto(event):
    identidad = claims(event)
    tenant_id = identidad['tenant_id']
    cliente_id = (event.get('pathParameters') or {}).get('cliente_id')
    if not cliente_id:
        raise ErrorNegocio(400, 'datos_incompletos', 'Falta el cliente')
    db = boto3.resource('dynamodb')
    cliente = db.Table(os.environ['TABLE_CLIENTES']).get_item(
        Key={'tenant_id': tenant_id, 'cliente_id': cliente_id}, ConsistentRead=True).get('Item')
    if not cliente or cliente.get('eliminado'):
        raise ErrorNegocio(404, 'no_encontrado', 'El cliente no existe')
    return identidad, cliente_id, db.Table(os.environ['TABLE_DOCUMENTOS'])


@manejar_errores
def subir(event, context):
    identidad, cliente_id, tabla = contexto(event)
    body = leer_body(event)
    nombre = body.get('nombre')
    contenido = body.get('contenido_base64')
    if (not isinstance(nombre, str) or not nombre.strip() or len(nombre) > 200
            or any(ord(c) < 32 or c in '/\\' for c in nombre)):
        raise ErrorNegocio(400, 'nombre_invalido', 'Indique un nombre de archivo válido')
    if not isinstance(contenido, str) or len(contenido) > 4 * ((MAX_BYTES + 2) // 3):
        raise ErrorNegocio(400, 'archivo_invalido', 'El archivo debe pesar como máximo 4 MB')
    try:
        datos = base64.b64decode(contenido, validate=True)
    except (ValueError, binascii.Error):
        raise ErrorNegocio(400, 'archivo_invalido', 'El contenido del archivo no es válido')
    if not datos or len(datos) > MAX_BYTES:
        raise ErrorNegocio(400, 'archivo_invalido', 'El archivo debe tener contenido y pesar como máximo 4 MB')

    documento_id = generar_id('doc')
    tenant_id = identidad['tenant_id']
    clave = f'{tenant_id}/{cliente_id}/{documento_id}'
    item = {'tenant_id': tenant_id, 'cliente_id': cliente_id, 'documento_id': documento_id,
            'nombre': nombre.strip(), 'tamano': len(datos), 'fecha_creacion': ahora(),
            'usuario_id': identidad['usuario_id'], 'clave_s3': clave}
    s3 = boto3.client('s3')
    bucket = os.environ['BUCKET_DOCUMENTOS']
    s3.put_object(Bucket=bucket, Key=clave, Body=datos, ContentType='application/octet-stream')
    try:
        tabla.put_item(Item=item, ConditionExpression='attribute_not_exists(documento_id)')
    except Exception:
        # Evita dejar archivos inaccesibles si falla el registro en DynamoDB.
        s3.delete_object(Bucket=bucket, Key=clave)
        raise
    return respuesta(201, {'documento': publico(item)})


def publico(item):
    return {k: v for k, v in item.items() if k not in ('clave_s3', 'tenant_id')}


@manejar_errores
def listar(event, context):
    identidad, cliente_id, tabla = contexto(event)
    params = event.get('queryStringParameters') or {}
    consulta = {'IndexName': 'cliente_id-index',
                'KeyConditionExpression': Key('tenant_id').eq(identidad['tenant_id']) & Key('cliente_id').eq(cliente_id),
                'Limit': 50}
    if params.get('siguiente'):
        consulta['ExclusiveStartKey'] = {'tenant_id': identidad['tenant_id'], 'cliente_id': cliente_id,
                                        'documento_id': params['siguiente']}
    pagina = tabla.query(**consulta)
    ultima = pagina.get('LastEvaluatedKey')
    return respuesta(200, {'documentos': [publico(item) for item in pagina.get('Items', [])],
                           'siguiente': ultima['documento_id'] if ultima else None})


@manejar_errores
def descargar(event, context):
    identidad, cliente_id, tabla = contexto(event)
    documento_id = (event.get('pathParameters') or {}).get('documento_id')
    if not documento_id:
        raise ErrorNegocio(400, 'datos_incompletos', 'Falta el documento')
    item = tabla.get_item(Key={'tenant_id': identidad['tenant_id'], 'documento_id': documento_id},
                          ConsistentRead=True).get('Item')
    if not item or item.get('cliente_id') != cliente_id:
        raise ErrorNegocio(404, 'no_encontrado', 'El documento no existe')
    url = boto3.client('s3').generate_presigned_url(
        'get_object', Params={'Bucket': os.environ['BUCKET_DOCUMENTOS'], 'Key': item['clave_s3'],
                              'ResponseContentDisposition': "attachment; filename*=UTF-8''" + quote(item['nombre'], safe='')},
        ExpiresIn=60)
    return respuesta(200, {'url': url})
