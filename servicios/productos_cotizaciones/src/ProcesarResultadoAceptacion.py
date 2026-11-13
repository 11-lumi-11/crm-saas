"""Aplica la decisión de Oportunidades y publica la aceptación confirmada."""
import json
import os

from crm_comun import ahora
from crm_comun.eventos import evento_pendiente, serializar
from src.utilidades import dynamodb_cliente, tabla


def procesar(evento):
    tipo, tenant, datos = evento['tipo'], evento['tenant_id'], evento['datos']
    if tipo not in ('oportunidad.aceptacion_confirmada', 'oportunidad.aceptacion_rechazada'):
        raise ValueError('Tipo inválido')
    clave = {'tenant_id': tenant, 'cotizacion_id': datos['cotizacion_id']}
    cotizacion = tabla('TABLE_COTIZACIONES').get_item(Key=clave, ConsistentRead=True).get('Item')
    if not cotizacion:
        raise ValueError('Cotización inexistente')
    if cotizacion.get('solicitud_aceptacion_id') != datos['solicitud_id']:
        return  # Respuesta tardía de una solicitud anterior.
    confirmado = tipo == 'oportunidad.aceptacion_confirmada'
    nuevo = 'aceptada' if confirmado else 'enviada'
    if cotizacion['estado'] == nuevo and cotizacion.get('resultado_solicitud_id') == datos['solicitud_id']:
        return
    fecha = ahora()
    valores = {':nuevo': nuevo, ':pendiente': 'aceptacion_pendiente', ':fecha': fecha,
               ':solicitud': datos['solicitud_id'], ':motivo': datos.get('motivo', '')}
    operaciones = [{'Update': {'TableName': os.environ['TABLE_COTIZACIONES'], 'Key': serializar(clave),
        'UpdateExpression': 'SET #estado = :nuevo, fecha_actualizacion = :fecha, fecha_resultado_aceptacion = :fecha, '
                            'resultado_solicitud_id = :solicitud, resultado_aceptacion = :motivo'
                            + (', fecha_respuesta = :fecha' if confirmado else ''),
        'ConditionExpression': '#estado = :pendiente AND solicitud_aceptacion_id = :solicitud',
        'ExpressionAttributeNames': {'#estado': 'estado'}, 'ExpressionAttributeValues': serializar(valores)}}]
    if confirmado:
        operaciones.append(evento_pendiente('cotizacion.aceptada', tenant, {
            'cotizacion_id': clave['cotizacion_id'], 'oportunidad_id': cotizacion['oportunidad_id'],
            'cliente_id': cotizacion['cliente_id'], 'total': cotizacion['total']}))
    dynamodb_cliente.transact_write_items(TransactItems=operaciones)


def lambda_handler(event, context):
    fallidos = []
    for registro in event.get('Records', []):
        try:
            procesar(json.loads(json.loads(registro['body'])['Message']))
        except Exception:
            fallidos.append({'itemIdentifier': registro['messageId']})
    return {'batchItemFailures': fallidos}
