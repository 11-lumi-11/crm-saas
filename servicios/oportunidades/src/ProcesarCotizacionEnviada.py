"""La primera cotización enviada inicia la negociación."""
import json
from crm_comun import registrar_fallo
from src.utilidades import ErrorNegocio, cambiar_etapa, leer_oportunidad


def procesar(evento):
    if evento['tipo'] != 'cotizacion.enviada':
        raise ValueError('Evento no admitido')
    tenant = evento['tenant_id']
    datos = evento['datos']
    try:
        oportunidad = leer_oportunidad(tenant, datos['oportunidad_id'])
        if oportunidad['cliente_id'] != datos['cliente_id']:
            raise ValueError('Cliente no coincide con la oportunidad')
        if oportunidad['etapa'] != 'nueva':
            return
        cambiar_etapa(tenant, datos['oportunidad_id'], 'en_negociacion', None, 'sistema')
    except ErrorNegocio as error:
        if error.codigo in ('oportunidad_cerrada', 'transicion_invalida'):
            return
        raise


def lambda_handler(event, context):
    fallidos = []
    for registro in event.get('Records', []):
        try:
            procesar(json.loads(json.loads(registro['body'])['Message']))
        except Exception as error:
            registrar_fallo('procesar_cotizacion_enviada', error, registro.get('messageId'))
            fallidos.append({'itemIdentifier': registro['messageId']})
    return {'batchItemFailures': fallidos}
