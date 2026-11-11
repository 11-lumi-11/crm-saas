"""Outbox: el dato de negocio y su evento se confirman en la misma transacción."""
import json
import os
import time

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer

from crm_comun import ahora, generar_id, convertir_decimal


def serializar(datos):
    serializador = TypeSerializer()
    return {k: serializador.serialize(v) for k, v in datos.items()}


def put(tabla, item, condicion=None):
    operacion = {'TableName': tabla, 'Item': serializar(item)}
    if condicion:
        operacion['ConditionExpression'] = condicion
    return {'Put': operacion}


def evento_pendiente(tipo, tenant_id, datos):
    evento = {'evento_id': generar_id('evt'), 'tipo': tipo, 'tenant_id': tenant_id,
              'fecha': ahora(), 'datos': datos}
    return put(os.environ['TABLE_EVENTOS'], {
        'evento_id': evento['evento_id'], 'tenant_id': tenant_id, 'estado': 'pendiente',
        'fecha_creacion': evento['fecha'], 'evento': evento,
    }, 'attribute_not_exists(evento_id)')


def confirmar(operaciones, tipo, tenant_id, datos):
    boto3.client('dynamodb').transact_write_items(
        TransactItems=[*operaciones, evento_pendiente(tipo, tenant_id, datos)])


def lambda_handler(event, context):
    """Publicación al menos una vez. Un fallo conserva el evento pendiente para la próxima ejecución."""
    tabla = boto3.resource('dynamodb').Table(os.environ['TABLE_EVENTOS'])
    sns = boto3.client('sns')
    consulta = {'IndexName': 'estado-fecha-index',
                'KeyConditionExpression': Key('estado').eq('pendiente'), 'Limit': 100}
    enviados = 0
    while True:
        pagina = tabla.query(**consulta)
        for item in pagina.get('Items', []):
            if context and context.get_remaining_time_in_millis() < 5000:
                return {'enviados': enviados}
            evento = item['evento']
            try:
                sns.publish(TopicArn=os.environ['SNS_TOPIC_ARN'],
                            Message=json.dumps(evento, default=convertir_decimal),
                            MessageAttributes={'tipo': {'DataType': 'String', 'StringValue': evento['tipo']}})
                tabla.update_item(Key={'evento_id': item['evento_id']},
                                  UpdateExpression='SET #estado = :enviado, expira_en = :ttl',
                                  ExpressionAttributeNames={'#estado': 'estado'},
                                  ExpressionAttributeValues={':enviado': 'enviado', ':ttl': int(time.time()) + 604800})
                enviados += 1
            except Exception:
                # No registrar payloads ni secretos. El registro permanece pendiente.
                print(f"Publicación pendiente: {item['evento_id']}")
        if not pagina.get('LastEvaluatedKey'):
            break
        consulta['ExclusiveStartKey'] = pagina['LastEvaluatedKey']
    return {'enviados': enviados}
