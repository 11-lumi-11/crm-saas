import os
import math
from decimal import Decimal
from datetime import datetime

import boto3
from boto3.dynamodb.types import TypeSerializer

from crm_comun import (
    ErrorNegocio, respuesta, manejar_errores, leer_body,
    obtener_claims, ahora, generar_id, validar_texto, validar_responsable
)
from crm_comun.eventos import confirmar, put, evento_pendiente

ETAPAS = ('nueva', 'calificada', 'propuesta', 'en_negociacion', 'ganada', 'perdida')
ETAPAS_CERRADAS = ('ganada', 'perdida')
# 'ganada' y 'perdida' comparten el nivel final; 'perdida' se valida aparte
ORDEN = {'nueva': 0, 'calificada': 1, 'propuesta': 2, 'en_negociacion': 3, 'ganada': 4, 'perdida': 4}
PROBABILIDAD_ETAPA = {
    'nueva': 10, 'calificada': 25, 'propuesta': 50,
    'en_negociacion': 75, 'ganada': 100, 'perdida': 0
}
MONEDAS = ('PEN', 'USD')
MONTO_MAXIMO = 10 ** 12

# Recursos a nivel de módulo (se reutilizan entre invocaciones)
dynamodb = boto3.resource('dynamodb')
dynamodb_cliente = boto3.client('dynamodb')  # transact_write_items solo existe en el cliente
serializador = TypeSerializer()


# ---------- Validaciones ----------

def validar_numero(valor, nombre, minimo, maximo):
    # bool es subclase de int; NaN/Infinity romperían Decimal o DynamoDB
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErrorNegocio(400, 'datos_invalidos', f'{nombre} debe ser un número')
    if isinstance(valor, float) and not math.isfinite(valor):
        raise ErrorNegocio(400, 'datos_invalidos', f'{nombre} debe ser un número finito')
    if valor < minimo or valor > maximo:
        raise ErrorNegocio(400, 'datos_invalidos', f'{nombre} debe estar entre {minimo} y {maximo}')
    return Decimal(str(valor))


def validar_monto(valor):
    return validar_numero(valor, 'monto_estimado', 0, MONTO_MAXIMO)


def validar_probabilidad(valor):
    return validar_numero(valor, 'probabilidad', 0, 100)


def validar_moneda(valor):
    if not isinstance(valor, str) or valor.strip().upper() not in MONEDAS:
        raise ErrorNegocio(400, 'datos_invalidos', 'moneda debe ser PEN o USD')
    return valor.strip().upper()


def validar_fecha_cierre(valor):
    texto = validar_texto(valor, 'fecha_cierre_estimada')
    try:
        datetime.fromisoformat(texto.replace('Z', '+00:00'))
    except ValueError:
        raise ErrorNegocio(400, 'datos_invalidos', 'fecha_cierre_estimada debe tener formato ISO 8601')
    return texto


# ---------- Acceso a datos ----------

def tabla(variable_entorno):
    return dynamodb.Table(os.environ[variable_entorno])


def leer_oportunidad(tenant_id, oportunidad_id):
    item = tabla('TABLE_OPORTUNIDADES').get_item(
        Key={'tenant_id': tenant_id, 'oportunidad_id': oportunidad_id}
    ).get('Item')
    if not item or item.get('eliminado'):
        raise ErrorNegocio(404, 'no_encontrado', 'La oportunidad no existe')
    return item


# ---------- Cambio de etapa (compartido por CambiarEtapa y el consumidor SQS) ----------

def cambiar_etapa(tenant_id, oportunidad_id, etapa_nueva, motivo_perdida, usuario_id):
    if not isinstance(etapa_nueva, str) or etapa_nueva not in ETAPAS:
        raise ErrorNegocio(400, 'etapa_invalida', 'Etapa no permitida')

    oportunidad = leer_oportunidad(tenant_id, oportunidad_id)
    etapa_actual = oportunidad['etapa']

    if etapa_actual in ETAPAS_CERRADAS:
        raise ErrorNegocio(409, 'oportunidad_cerrada', 'La oportunidad ya está cerrada')

    if etapa_nueva == 'perdida':
        if not isinstance(motivo_perdida, str) or not motivo_perdida.strip():
            raise ErrorNegocio(400, 'motivo_requerido', 'Indique el motivo de la pérdida')
        motivo_perdida = motivo_perdida.strip()
    elif ORDEN[etapa_nueva] <= ORDEN[etapa_actual]:
        raise ErrorNegocio(400, 'transicion_invalida', 'Solo se puede avanzar a una etapa posterior')

    probabilidad = PROBABILIDAD_ETAPA[etapa_nueva]
    fecha = ahora()

    expresion = 'SET #etapa = :nueva, probabilidad = :prob, fecha_actualizacion = :fecha'
    valores = {':nueva': etapa_nueva, ':prob': probabilidad, ':fecha': fecha, ':actual': etapa_actual}
    if etapa_nueva == 'perdida':
        expresion += ', motivo_perdida = :motivo'
        valores[':motivo'] = motivo_perdida

    historial = {
        'tenant_id': tenant_id,
        'historial_id': generar_id('his'),
        'oportunidad_id': oportunidad_id,
        'etapa_anterior': etapa_actual,
        'etapa_nueva': etapa_nueva,
        'usuario_id': usuario_id,
        'fecha_cambio': fecha
    }

    # Evento: al cerrar solo se publica ganada/perdida, nunca además etapa_cambiada
    if etapa_nueva == 'ganada':
        tipo, datos_evento = 'oportunidad.ganada', {
            'oportunidad_id': oportunidad_id,
            'cliente_id': oportunidad['cliente_id'],
            'titulo': oportunidad['titulo'],
            'monto_estimado': oportunidad['monto_estimado'],
            'responsable_id': oportunidad['responsable_id']
        }
    elif etapa_nueva == 'perdida':
        tipo, datos_evento = 'oportunidad.perdida', {
            'oportunidad_id': oportunidad_id,
            'cliente_id': oportunidad['cliente_id'],
            'motivo_perdida': motivo_perdida,
            'responsable_id': oportunidad['responsable_id']
        }
    else:
        tipo, datos_evento = 'oportunidad.etapa_cambiada', {
            'oportunidad_id': oportunidad_id,
            'cliente_id': oportunidad['cliente_id'],
            'etapa_anterior': etapa_actual,
            'etapa_nueva': etapa_nueva,
            'responsable_id': oportunidad['responsable_id']
        }


    try:
        dynamodb_cliente.transact_write_items(TransactItems=[
            {
                'Update': {
                    'TableName': os.environ['TABLE_OPORTUNIDADES'],
                    'Key': {
                        'tenant_id': serializador.serialize(tenant_id),
                        'oportunidad_id': serializador.serialize(oportunidad_id)
                    },
                    'UpdateExpression': expresion,
                    'ConditionExpression': '#etapa = :actual AND attribute_not_exists(fecha_eliminacion)',
                    'ExpressionAttributeNames': {'#etapa': 'etapa'},
                    'ExpressionAttributeValues': {k: serializador.serialize(v) for k, v in valores.items()}
                }
            },
            {
                'Put': {
                    'TableName': os.environ['TABLE_HISTORIAL'],
                    'Item': {k: serializador.serialize(v) for k, v in historial.items()}
                }
            },
            evento_pendiente(tipo, tenant_id, datos_evento)
        ])
    except dynamodb_cliente.exceptions.TransactionCanceledException as e:
        razones = e.response.get('CancellationReasons', [])
        if razones and razones[0].get('Code') == 'ConditionalCheckFailed':
            leer_oportunidad(tenant_id, oportunidad_id)
            raise ErrorNegocio(409, 'conflicto_etapa', 'La oportunidad cambió de etapa mientras se procesaba; reintente')
        raise

    oportunidad.update({'etapa': etapa_nueva, 'probabilidad': Decimal(probabilidad), 'fecha_actualizacion': fecha})
    if etapa_nueva == 'perdida':
        oportunidad['motivo_perdida'] = motivo_perdida
    return oportunidad

__all__ = ['ErrorNegocio', 'respuesta', 'manejar_errores', 'leer_body', 'obtener_claims',
           'ahora', 'generar_id', 'validar_texto', 'validar_responsable', 'confirmar', 'put']
