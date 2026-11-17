"""Añade destinatarios propios al evento de venta sin consultar otros servicios."""
import json
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError
from crm_comun import registrar_fallo
from crm_comun.eventos import evento_pendiente, put

db = boto3.resource('dynamodb')
dynamodb = boto3.client('dynamodb')


def procesar(evento):
    if evento['tipo'] != 'cotizacion.aceptada':
        raise ValueError('Evento no admitido')
    tenant, datos = evento['tenant_id'], evento['datos']
    cliente_id = datos['cliente_id']
    tabla = db.Table(os.environ['TABLE_CLIENTES'])
    cliente = tabla.get_item(Key={'tenant_id': tenant, 'cliente_id': cliente_id}, ConsistentRead=True).get('Item')
    if not cliente:
        raise ValueError('Cliente de la venta no encontrado')
    contacto = {}
    if cliente.get('contacto_principal_id'):
        contacto = db.Table(os.environ['TABLE_CONTACTOS']).get_item(
            Key={'tenant_id': tenant, 'contacto_id': cliente['contacto_principal_id']}, ConsistentRead=True).get('Item') or {}
        if not contacto:
            raise ValueError('Contacto principal no encontrado')
    destinatarios = {'cliente_id': cliente_id, 'cotizacion_id': datos['cotizacion_id'],
        'total': datos['total'], 'moneda': datos.get('moneda', 'PEN'), 'venta_evento_id': evento['evento_id'],
        'correo_cliente': cliente.get('correo', ''), 'revision_correo': cliente.get('revision_correo', 0),
        'contacto_id': cliente.get('contacto_principal_id', ''), 'correo_principal': contacto.get('correo', '')}
    recibido = {'tenant_id': tenant, 'evento_id': evento['evento_id']}
    try:
        dynamodb.transact_write_items(TransactItems=[
            put(os.environ['TABLE_VENTAS_RECIBIDAS'], recibido, 'attribute_not_exists(evento_id)'),
            evento_pendiente('venta.destinatarios', tenant, destinatarios)])
    except ClientError as error:
        razones = error.response.get('CancellationReasons', [])
        if error.response['Error']['Code'] == 'TransactionCanceledException' and razones and razones[0].get('Code') == 'ConditionalCheckFailed':
            return
        raise


def lambda_handler(event, context):
    fallidos = []
    for registro in event.get('Records', []):
        try:
            procesar(json.loads(json.loads(registro['body'])['Message'], parse_float=Decimal))
        except Exception as error:
            registrar_fallo('preparar_correo_venta', error, registro.get('messageId'))
            fallidos.append({'itemIdentifier': registro['messageId']})
    return {'batchItemFailures': fallidos}
