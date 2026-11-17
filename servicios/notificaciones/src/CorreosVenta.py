"""Suscripciones SNS aisladas por destinatario y avisos sencillos de venta."""
import hashlib
import json
import os
import re

import boto3
from botocore.exceptions import ClientError
from crm_comun import registrar_fallo

db = boto3.resource('dynamodb')
sns = boto3.client('sns')


def huella(*partes):
    return hashlib.sha256(json.dumps(partes, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def tabla():
    return db.Table(os.environ['TABLE_CORREOS_VENTA'])


def clave(tenant, cliente):
    return {'tenant_id': tenant, 'clave': 'cliente#' + cliente}


def topic(tenant, cliente, correo):
    # Cada dirección y cliente tiene un topic independiente, incluso en distintos tenants.
    nombre = f"{os.environ['STAGE']}-venta-{huella(tenant, cliente, correo)[:40]}"
    return sns.create_topic(Name=nombre)['TopicArn']


def filtro(tenant, cliente, correo):
    return huella(tenant, cliente, correo)


def suscribir(tenant, cliente, correo):
    arn = topic(tenant, cliente, correo)
    respuesta = sns.subscribe(TopicArn=arn, Protocol='email', Endpoint=correo,
        Attributes={'FilterPolicy': json.dumps({'destino': [filtro(tenant, cliente, correo)]})},
        ReturnSubscriptionArn=True)
    return {'correo': correo, 'topic_arn': arn, 'subscription_arn': respuesta['SubscriptionArn']}


def actualizar_destinatario(evento):
    tenant, datos = evento['tenant_id'], evento['datos']
    cliente = datos['cliente_id']
    tipo = evento['tipo']
    campo = 'cliente' if tipo == 'cliente.correo_actualizado' else 'principal'
    correo = datos['correo'].strip().lower()
    if correo and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', correo):
        raise ValueError('Correo de destinatario inválido')
    key = clave(tenant, cliente)
    actual = tabla().get_item(Key=key, ConsistentRead=True).get('Item', {})
    previo = actual.get(campo) or {}
    revision = int(datos['revision']) if campo == 'cliente' else 1
    if revision <= int(actual.get(campo + '_revision', 0)):
        return
    otro = actual.get('principal' if campo == 'cliente' else 'cliente') or {}
    if correo and correo == previo.get('correo'):
        nuevo = previo
    elif correo and correo == otro.get('correo'):
        nuevo = otro
    elif correo:
        nuevo = suscribir(tenant, cliente, correo)
    else:
        nuevo = {}
    if campo == 'principal':
        nuevo = {**nuevo, 'contacto_id': datos['contacto_id']}
    # SQS se procesa con concurrencia 1; la revisión evita aplicar eventos antiguos.
    tabla().update_item(Key=key, UpdateExpression='SET #campo = :destino, #revision = :revision',
        ExpressionAttributeNames={'#campo': campo, '#revision': campo + '_revision'},
        ExpressionAttributeValues={':destino': nuevo, ':revision': revision})
    if previo and previo.get('correo') != correo and previo.get('correo') != otro.get('correo'):
        try:
            sns.unsubscribe(SubscriptionArn=previo['subscription_arn'])
        except ClientError as error:
            # Una suscripción sin confirmar puede no admitir eliminación; su topic ya no recibe ventas.
            registrar_fallo('retirar_suscripcion_correo', error)


def avisar_venta(evento):
    tenant, datos = evento['tenant_id'], evento['datos']
    cliente = datos['cliente_id']
    estado = tabla().get_item(Key=clave(tenant, cliente), ConsistentRead=True).get('Item')
    if estado is None:
        raise ValueError('Destinatarios del cliente aún no registrados')
    revision_venta = int(datos['revision_correo'])
    revision_actual = int(estado.get('cliente_revision', 0))
    if revision_actual < revision_venta:
        raise ValueError('Cambio de correo aún no procesado')
    destinatarios = {}
    cliente_actual = estado.get('cliente') or {}
    if revision_actual == revision_venta and datos['correo_cliente']:
        if cliente_actual.get('correo') != datos['correo_cliente']:
            raise ValueError('Correo de cliente no coincide')
        destinatarios[cliente_actual['correo']] = cliente_actual
    if datos['contacto_id']:
        principal = estado.get('principal') or {}
        if principal.get('contacto_id') != datos['contacto_id']:
            raise ValueError('Contacto principal aún no procesado')
        if datos['correo_principal']:
            if principal.get('correo') != datos['correo_principal']:
                raise ValueError('Correo de contacto no coincide')
            destinatarios[principal['correo']] = principal
    for correo, destino in destinatarios.items():
        entrega = {'tenant_id': tenant, 'clave': 'venta#' + huella(datos['venta_evento_id'], cliente, correo)}
        if tabla().get_item(Key=entrega, ConsistentRead=True).get('Item'):
            continue
        mensaje = (f"Venta confirmada.\nCotización: {datos['cotizacion_id']}\n"
                   f"Total: {datos['total']} {datos.get('moneda', '')}".strip())
        sns.publish(TopicArn=destino['topic_arn'], Subject='Venta confirmada', Message=mensaje,
            MessageAttributes={'destino': {'DataType': 'String', 'StringValue': filtro(tenant, cliente, correo)}})
        tabla().put_item(Item=entrega)


def lambda_handler(event, context):
    fallidos = []
    for registro in event.get('Records', []):
        try:
            evento = json.loads(json.loads(registro['body'])['Message'])
            if evento['tipo'] in ('cliente.correo_actualizado', 'cliente.contacto_principal_creado'):
                actualizar_destinatario(evento)
            elif evento['tipo'] == 'venta.destinatarios':
                avisar_venta(evento)
            else:
                raise ValueError('Tipo de evento no admitido')
        except Exception as error:
            registrar_fallo('procesar_correo_venta', error, registro.get('messageId'))
            fallidos.append({'itemIdentifier': registro['messageId']})
    return {'batchItemFailures': fallidos}
