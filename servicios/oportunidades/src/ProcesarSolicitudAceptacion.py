"""Decide una solicitud una sola vez y conserva la respuesta en el outbox."""
import json
import os
import re

from crm_comun import ahora
from crm_comun.eventos import evento_pendiente, put, serializar
from src.utilidades import dynamodb, dynamodb_cliente, cambiar_etapa


def procesar(evento):
    if evento.get('tipo') != 'cotizacion.aceptacion_solicitada':
        raise ValueError('Tipo inválido')
    tenant = evento['tenant_id']
    datos = evento['datos']
    solicitud = datos['solicitud_id']
    for valor, prefijo in ((tenant, 'ten'), (solicitud, 'sol'),
                           (datos['oportunidad_id'], 'opo'), (datos['cotizacion_id'], 'cot'),
                           (datos['cliente_id'], 'cli')):
        if not isinstance(valor, str) or not re.fullmatch(rf'{prefijo}_[A-Za-z0-9]+', valor):
            raise ValueError('Identificador inválido')
    tabla_decisiones = dynamodb.Table(os.environ['TABLE_SOLICITUDES'])
    clave = {'tenant_id': tenant, 'solicitud_id': solicitud}
    if tabla_decisiones.get_item(Key=clave, ConsistentRead=True).get('Item'):
        return
    oportunidad = dynamodb.Table(os.environ['TABLE_OPORTUNIDADES']).get_item(
        Key={'tenant_id': tenant, 'oportunidad_id': datos['oportunidad_id']}, ConsistentRead=True).get('Item')
    motivo = None
    if not oportunidad or oportunidad.get('eliminado'):
        motivo = 'La oportunidad no existe o está archivada.'
    elif oportunidad['etapa'] == 'perdida':
        motivo = 'No se puede aceptar la cotización porque la oportunidad está marcada como perdida.'
    elif oportunidad['etapa'] == 'ganada':
        motivo = 'No se puede aceptar la cotización porque la oportunidad ya está ganada.'
    elif oportunidad['cliente_id'] != datos['cliente_id']:
        motivo = 'El cliente de la cotización no coincide con el de la oportunidad.'

    tipo = 'oportunidad.aceptacion_rechazada' if motivo else 'oportunidad.aceptacion_confirmada'
    respuesta = {**datos, 'motivo': motivo or ''}
    adicionales = [put(os.environ['TABLE_SOLICITUDES'], {**clave, 'resultado': tipo,
                    'fecha_creacion': ahora()}, 'attribute_not_exists(solicitud_id)'),
                   evento_pendiente(tipo, tenant, respuesta)]
    if motivo:
        # Condición sobre la versión observada: si cambia, reintentar la decisión.
        condicion = {'TableName': os.environ['TABLE_OPORTUNIDADES'],
                     'Key': serializar({'tenant_id': tenant, 'oportunidad_id': datos['oportunidad_id']})}
        if not oportunidad:
            condicion['ConditionExpression'] = 'attribute_not_exists(oportunidad_id)'
        else:
            condicion.update(ConditionExpression='#etapa = :etapa AND cliente_id = :cliente AND '
                + ('attribute_exists(fecha_eliminacion)' if oportunidad.get('eliminado') else 'attribute_not_exists(fecha_eliminacion)'),
                ExpressionAttributeNames={'#etapa': 'etapa'},
                ExpressionAttributeValues=serializar({':etapa': oportunidad['etapa'], ':cliente': oportunidad['cliente_id']}))
        dynamodb_cliente.transact_write_items(TransactItems=[{'ConditionCheck': condicion}, *adicionales])
    else:
        cambiar_etapa(tenant, datos['oportunidad_id'], 'ganada', None, 'sistema', adicionales)


def lambda_handler(event, context):
    fallidos = []
    for registro in event.get('Records', []):
        try:
            sobre = json.loads(registro['body'])
            procesar(json.loads(sobre['Message']))
        except Exception:
            fallidos.append({'itemIdentifier': registro['messageId']})
    return {'batchItemFailures': fallidos}
