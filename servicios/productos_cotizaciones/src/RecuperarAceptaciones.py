"""Reprograma solicitudes pendientes sin volver a decidir su resultado."""
import os
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from crm_comun.eventos import evento_pendiente, serializar
from crm_comun import registrar_excepciones


def fecha(valor):
    return valor.strftime('%Y-%m-%dT%H:%M:%SZ')


@registrar_excepciones
def lambda_handler(event, context):
    instante = datetime.now(timezone.utc)
    limite = fecha(instante)
    siguiente = fecha(instante + timedelta(minutes=10))
    tabla = boto3.resource('dynamodb').Table(os.environ['TABLE_COTIZACIONES'])
    cliente = boto3.client('dynamodb')
    consulta = {'IndexName': 'recuperacion-aceptacion-index',
                'KeyConditionExpression': Key('recuperacion_estado').eq('pendiente') & Key('proximo_reintento').lte(limite),
                'Limit': 100}
    reenviadas = 0
    while True:
        pagina = tabla.query(**consulta)
        for item in pagina.get('Items', []):
            if context and context.get_remaining_time_in_millis() < 5000:
                return {'reenviadas': reenviadas}
            datos = {'cotizacion_id': item['cotizacion_id'], 'oportunidad_id': item['oportunidad_id'],
                     'cliente_id': item['cliente_id'], 'solicitud_id': item['solicitud_aceptacion_id']}
            update = {'TableName': os.environ['TABLE_COTIZACIONES'],
                      'Key': serializar({'tenant_id': item['tenant_id'], 'cotizacion_id': item['cotizacion_id']}),
                      'UpdateExpression': 'SET proximo_reintento = :siguiente',
                      'ConditionExpression': '#estado = :pendiente AND solicitud_aceptacion_id = :solicitud AND proximo_reintento = :anterior',
                      'ExpressionAttributeNames': {'#estado': 'estado'},
                      'ExpressionAttributeValues': serializar({':pendiente': 'aceptacion_pendiente',
                          ':solicitud': datos['solicitud_id'], ':anterior': item['proximo_reintento'], ':siguiente': siguiente})}
            try:
                cliente.transact_write_items(TransactItems=[{'Update': update},
                    evento_pendiente('cotizacion.aceptacion_solicitada', item['tenant_id'], datos)])
                reenviadas += 1
            except ClientError as error:
                razones = error.response.get('CancellationReasons', [])
                if not (error.response['Error']['Code'] == 'TransactionCanceledException' and razones and
                        razones[0].get('Code') == 'ConditionalCheckFailed'):
                    raise
        if not pagina.get('LastEvaluatedKey'):
            break
        consulta['ExclusiveStartKey'] = pagina['LastEvaluatedKey']
    return {'reenviadas': reenviadas}
