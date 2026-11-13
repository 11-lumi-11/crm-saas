"""Validaciones, acceso a datos y transiciones de cotización compartidas por los handlers."""
import math
import os
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

import boto3
from boto3.dynamodb.types import TypeSerializer

from crm_comun import (
    ErrorNegocio, respuesta, manejar_errores, leer_body,
    obtener_claims, ahora, generar_id, validar_texto
)
from crm_comun.eventos import confirmar, put, evento_pendiente

MONEDAS = ('PEN', 'USD')
ESTADOS_PRODUCTO = ('activo', 'inactivo')
ESTADOS_COTIZACION = ('borrador', 'enviada', 'aceptacion_pendiente', 'aceptada', 'rechazada')
ROLES_GESTION = ('gerente', 'admin')
PRECIO_MAXIMO = 10 ** 12
CANTIDAD_MAXIMA = 100_000
ITEMS_MAXIMOS = 50
DIAS_VIGENCIA = 15
CENTIMOS = Decimal('0.01')

# Recursos a nivel de módulo (se reutilizan entre invocaciones)
dynamodb = boto3.resource('dynamodb')
dynamodb_cliente = boto3.client('dynamodb')  # transact_write_items solo existe en el cliente
serializador = TypeSerializer()


# ---------- Permisos ----------

def exigir_gestion(rol, accion):
    if rol not in ROLES_GESTION:
        raise ErrorNegocio(403, 'prohibido', f'Solo gerente o admin puede {accion}')


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


def validar_precio(valor):
    return validar_numero(valor, 'precio', 0, PRECIO_MAXIMO).quantize(CENTIMOS, ROUND_HALF_UP)


def validar_cantidad(valor):
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErrorNegocio(400, 'datos_invalidos', 'cantidad debe ser un número entero')
    return validar_numero(valor, 'cantidad', 1, CANTIDAD_MAXIMA)


def validar_moneda(valor):
    if not isinstance(valor, str) or valor.strip().upper() not in MONEDAS:
        raise ErrorNegocio(400, 'datos_invalidos', 'moneda debe ser PEN o USD')
    return valor.strip().upper()


def validar_estado_producto(valor):
    if valor not in ESTADOS_PRODUCTO:
        raise ErrorNegocio(400, 'estado_invalido', 'estado debe ser activo o inactivo')
    return valor


def validar_texto_opcional(valor, campo):
    if not isinstance(valor, str):
        raise ErrorNegocio(400, 'datos_invalidos', f'{campo} debe ser texto')
    return valor.strip()


def validar_id(valor, campo, prefijo):
    if not isinstance(valor, str) or not re.fullmatch(rf'{prefijo}_[a-zA-Z0-9]+', valor):
        raise ErrorNegocio(400, 'datos_invalidos', f'{campo} debe tener prefijo {prefijo}_ y caracteres alfanuméricos')
    return valor


def validar_fecha_vencimiento(valor):
    texto = validar_texto(valor, 'fecha_vencimiento')
    try:
        fecha = datetime.fromisoformat(texto.replace('Z', '+00:00'))
    except ValueError:
        raise ErrorNegocio(400, 'datos_invalidos', 'fecha_vencimiento debe tener formato ISO 8601')
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    if fecha <= datetime.now(timezone.utc):
        raise ErrorNegocio(400, 'datos_invalidos', 'fecha_vencimiento debe ser futura')
    return fecha.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def vencimiento_por_defecto():
    return (datetime.now(timezone.utc) + timedelta(days=DIAS_VIGENCIA)).strftime('%Y-%m-%dT%H:%M:%SZ')


def esta_vencida(cotizacion):
    fecha = datetime.fromisoformat(cotizacion['fecha_vencimiento'].replace('Z', '+00:00'))
    return fecha <= datetime.now(timezone.utc)


def leer_limite(params):
    try:
        return min(max(int(params.get('limite', 50)), 1), 100)
    except (TypeError, ValueError):
        raise ErrorNegocio(400, 'datos_invalidos', 'limite debe ser un número entero')


# ---------- Acceso a datos ----------

def tabla(variable_entorno):
    return dynamodb.Table(os.environ[variable_entorno])


def leer_producto(tenant_id, producto_id):
    item = tabla('TABLE_PRODUCTOS').get_item(
        Key={'tenant_id': tenant_id, 'producto_id': producto_id}).get('Item')
    if not item:
        raise ErrorNegocio(404, 'no_encontrado', 'El producto no existe')
    return item


def leer_cotizacion(tenant_id, cotizacion_id):
    item = tabla('TABLE_COTIZACIONES').get_item(
        Key={'tenant_id': tenant_id, 'cotizacion_id': cotizacion_id}).get('Item')
    if not item or item.get('eliminado'):
        raise ErrorNegocio(404, 'no_encontrado', 'La cotización no existe')
    return item


def leer_productos(tenant_id, producto_ids):
    """Lee varios productos del tenant en lotes de 100 (límite de BatchGetItem)."""
    encontrados, ids = {}, list(dict.fromkeys(producto_ids))
    for inicio in range(0, len(ids), 100):
        pendientes = {os.environ['TABLE_PRODUCTOS']: {'Keys': [
            {'tenant_id': tenant_id, 'producto_id': pid} for pid in ids[inicio:inicio + 100]]}}
        while pendientes:
            resultado = dynamodb.batch_get_item(RequestItems=pendientes)
            for item in resultado['Responses'].get(os.environ['TABLE_PRODUCTOS'], []):
                encontrados[item['producto_id']] = item
            pendientes = resultado.get('UnprocessedKeys') or None
    return encontrados


# ---------- Transiciones de estado de una cotización ----------

def cambiar_estado(tenant_id, cotizacion_id, estado_esperado, estado_nuevo, tipo_evento, datos_evento,
                   campos_fecha=(), extra=None):
    """Cambia el estado solo si sigue siendo el esperado y guarda el evento en el outbox, todo en una transacción."""
    fecha = ahora()
    expresion = 'SET #estado = :nuevo, fecha_actualizacion = :fecha'
    valores = {':nuevo': estado_nuevo, ':fecha': fecha, ':esperado': estado_esperado}
    for campo in campos_fecha:  # por ejemplo fecha_envio: toma la misma fecha del cambio
        expresion += f', {campo} = :fecha'
    for campo, valor in (extra or {}).items():
        expresion += f', {campo} = :{campo}'
        valores[f':{campo}'] = valor
    try:
        dynamodb_cliente.transact_write_items(TransactItems=[
            {'Update': {
                'TableName': os.environ['TABLE_COTIZACIONES'],
                'Key': {'tenant_id': serializador.serialize(tenant_id),
                        'cotizacion_id': serializador.serialize(cotizacion_id)},
                'UpdateExpression': expresion,
                'ConditionExpression': '#estado = :esperado AND attribute_not_exists(fecha_eliminacion)',
                'ExpressionAttributeNames': {'#estado': 'estado'},
                'ExpressionAttributeValues': {k: serializador.serialize(v) for k, v in valores.items()},
            }},
            evento_pendiente(tipo_evento, tenant_id, datos_evento),
        ])
    except dynamodb_cliente.exceptions.TransactionCanceledException as e:
        razones = e.response.get('CancellationReasons', [])
        if razones and razones[0].get('Code') == 'ConditionalCheckFailed':
            leer_cotizacion(tenant_id, cotizacion_id)  # 404 si se archivó
            raise ErrorNegocio(409, 'conflicto_estado', 'La cotización cambió de estado mientras se procesaba; reintente')
        raise
    return fecha


def exigir_estado(cotizacion, esperado, accion):
    if cotizacion['estado'] != esperado:
        raise ErrorNegocio(409, 'estado_invalido_cotizacion',
                           f'Solo se puede {accion} una cotización en estado {esperado}; '
                           f'esta está {cotizacion["estado"]}')


__all__ = ['ErrorNegocio', 'respuesta', 'manejar_errores', 'leer_body', 'obtener_claims',
           'ahora', 'generar_id', 'validar_texto', 'confirmar', 'put']
