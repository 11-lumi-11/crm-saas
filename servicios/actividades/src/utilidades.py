"""Reglas propias de Actividades; HTTP e identidad pertenecen a crm_comun."""
import base64
import functools
import json
import os
import re
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from crm_comun import (ErrorNegocio, respuesta, manejar_errores, leer_body,
                       obtener_claims, ahora, generar_id, validar_texto, validar_responsable)
from crm_comun.eventos import serializar, put

TIPOS = ('llamada', 'reunion', 'correo', 'tarea')
ESTADOS = ('pendiente', 'completada', 'cancelada')
dynamodb = boto3.resource('dynamodb')
cliente = boto3.client('dynamodb')


def endpoint(funcion):
    @manejar_errores
    @functools.wraps(funcion)
    def ejecutar(event, context):
        try:
            return funcion(event, context)
        except (ClientError, BotoCoreError):
            # No exponer errores de infraestructura ni payloads al cliente.
            return respuesta(503, {'codigo': 'servicio_no_disponible',
                                   'mensaje': 'No se pudo confirmar la operación; reintente'})
    return ejecutar


def tabla(variable='TABLE_ACTIVIDADES'):
    return dynamodb.Table(os.environ[variable])


def validar_id(valor, campo, prefijo):
    if not isinstance(valor, str) or not re.fullmatch(rf'{prefijo}_[A-Za-z0-9]+', valor):
        raise ErrorNegocio(400, 'datos_invalidos', f'{campo} debe tener prefijo {prefijo}_ y caracteres alfanuméricos')
    return valor


def fecha_utc(valor, campo='fecha_programada'):
    texto = validar_texto(valor, campo)
    try:
        if 'T' not in texto:
            raise ValueError()
        fecha = datetime.fromisoformat(texto.replace('Z', '+00:00'))
        if fecha.tzinfo is None:
            raise ValueError()
        return fecha.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except (ValueError, OverflowError):
        raise ErrorNegocio(400, 'datos_invalidos', f'{campo} debe ser ISO 8601 con zona horaria')


def tipo_valido(valor):
    if valor not in TIPOS:
        raise ErrorNegocio(400, 'tipo_invalido', 'Tipo de actividad no permitido')
    return valor


def descripcion_valida(valor):
    if not isinstance(valor, str) or len(valor) > 10000:
        raise ErrorNegocio(400, 'datos_invalidos', 'descripcion debe ser texto de hasta 10000 caracteres')
    return valor.strip()


def titulo_valido(valor):
    valor = validar_texto(valor, 'titulo')
    if len(valor) > 200:
        raise ErrorNegocio(400, 'datos_invalidos', 'titulo admite hasta 200 caracteres')
    return valor


def exigir_campos(body, permitidos):
    if set(body) - set(permitidos):
        raise ErrorNegocio(400, 'campo_no_editable', 'La petición contiene campos no permitidos')


def leer_actividad(tenant_id, actividad_id):
    validar_id(actividad_id, 'actividad_id', 'act')
    item = tabla().get_item(Key={'tenant_id': tenant_id, 'actividad_id': actividad_id},
                            ConsistentRead=True).get('Item')
    if not item:
        raise ErrorNegocio(404, 'no_encontrado', 'La actividad no existe')
    return item


def publica(item):
    return {k: v for k, v in item.items() if k not in ('version', 'evento_origen_id')}


def control(tenant_id, oportunidad_id):
    return tabla('TABLE_OPORTUNIDADES_CONTROL').get_item(
        Key={'tenant_id': tenant_id, 'oportunidad_id': oportunidad_id}, ConsistentRead=True).get('Item', {})


def proteger_oportunidad(tenant_id, oportunidad_id):
    """Escritura común para serializar creaciones con el cierre por pérdida."""
    return {'Update': {
        'TableName': os.environ['TABLE_OPORTUNIDADES_CONTROL'],
        'Key': serializar({'tenant_id': tenant_id, 'oportunidad_id': oportunidad_id}),
        'UpdateExpression': 'SET fecha_actualizacion = :fecha ADD revision :uno',
        'ConditionExpression': 'attribute_not_exists(perdida)',
        'ExpressionAttributeValues': serializar({':fecha': ahora(), ':uno': 1})}}


def comprobar_oportunidad(tenant_id, oportunidad_id):
    return {'ConditionCheck': {
        'TableName': os.environ['TABLE_OPORTUNIDADES_CONTROL'],
        'Key': serializar({'tenant_id': tenant_id, 'oportunidad_id': oportunidad_id}),
        'ConditionExpression': 'attribute_not_exists(perdida)'}}


def es_condicional(error):
    return (error.response['Error']['Code'] == 'ConditionalCheckFailedException' or
            (error.response['Error']['Code'] == 'TransactionCanceledException' and
             any(r.get('Code') == 'ConditionalCheckFailed'
                 for r in error.response.get('CancellationReasons', []))))


def conflicto(error, tenant_id, oportunidad_id=None):
    if not es_condicional(error):
        raise error
    if oportunidad_id and control(tenant_id, oportunidad_id).get('perdida'):
        raise ErrorNegocio(409, 'oportunidad_perdida', 'La oportunidad fue marcada como perdida')
    raise ErrorNegocio(409, 'conflicto_actividad', 'La actividad cambió mientras se procesaba; vuelva a consultar')


def nueva_actividad(tenant_id, actividad_id, tipo, titulo, descripcion, cliente_id,
                    oportunidad_id, responsable_id, fecha_programada, origen):
    fecha = ahora()
    item = dict(tenant_id=tenant_id, actividad_id=actividad_id, tipo=tipo, titulo=titulo,
                descripcion=descripcion, cliente_id=cliente_id, responsable_id=responsable_id,
                fecha_programada=fecha_programada, estado='pendiente', origen=origen,
                fecha_creacion=fecha, fecha_actualizacion=fecha, version=1)
    if oportunidad_id:
        item['oportunidad_id'] = oportunidad_id
    return item


def cursor_codificar(clave, consulta):
    return base64.urlsafe_b64encode(json.dumps({'clave': clave, 'consulta': consulta},
                                               separators=(',', ':')).encode()).decode()


def cursor_leer(valor, consulta, indice):
    try:
        if not isinstance(valor, str) or len(valor) > 4096:
            raise ValueError()
        datos = json.loads(base64.b64decode(valor, altchars=b'-_', validate=True))
        clave = datos['clave']
        esperadas = {'tenant_id', 'actividad_id', indice}
        if (datos['consulta'] != consulta or not isinstance(clave, dict) or
                set(clave) != esperadas or not all(isinstance(v, str) and v for v in clave.values()) or
                clave['tenant_id'] != consulta['tenant_id']):
            raise ValueError()
        if indice != 'fecha_programada' and clave[indice] != consulta[indice]:
            raise ValueError()
        validar_id(clave['actividad_id'], 'actividad_id', 'act')
        return clave
    except (ValueError, TypeError, KeyError, ErrorNegocio):
        raise ErrorNegocio(400, 'paginacion_invalida', 'siguiente no corresponde a esta consulta')
