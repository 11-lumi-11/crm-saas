"""SNS/SQS: deduplicación transaccional y barrera persistente ante oportunidades perdidas."""
import hashlib
import json
import os
from datetime import datetime, timedelta

from botocore.exceptions import ClientError
from crm_comun import ahora, validar_texto, validar_responsable, registrar_fallo
from crm_comun.eventos import put
from src.utilidades import (tabla, cliente, serializar, validar_id, fecha_utc,
    nueva_actividad, proteger_oportunidad, control, es_condicional)

EVENTOS = ('oportunidad.ganada',
           'oportunidad.perdida', 'cotizacion.enviada')


def leer_evento(registro):
    sobre = json.loads(registro['body'])
    if not isinstance(sobre, dict) or not isinstance(sobre.get('Message'), str):
        raise ValueError('Se esperaba el sobre SNS con Message JSON')
    evento = json.loads(sobre['Message'])
    if not isinstance(evento, dict) or evento.get('tipo') not in EVENTOS:
        raise ValueError('Tipo de evento no admitido')
    # Tenant se toma del evento confiado por la política SNS, nunca de datos.
    validar_texto(evento.get('tenant_id'), 'tenant_id')
    validar_id(evento.get('evento_id'), 'evento_id', 'evt')
    fecha_utc(evento.get('fecha'), 'fecha')
    datos = evento.get('datos')
    if not isinstance(datos, dict):
        raise ValueError('datos debe ser objeto')
    validar_id(datos.get('oportunidad_id'), 'oportunidad_id', 'opo')
    validar_id(datos.get('cliente_id'), 'cliente_id', 'cli')
    if evento['tipo'] == 'cotizacion.enviada':
        validar_id(datos.get('cotizacion_id'), 'cotizacion_id', 'cot')
        validar_responsable(datos.get('creada_por'))
        if isinstance(datos.get('total'), bool) or not isinstance(datos.get('total'), (int, float)):
            raise ValueError('total debe ser numérico')
    else:
        validar_responsable(datos.get('responsable_id'))
        if evento['tipo'] == 'oportunidad.perdida':
            validar_texto(datos.get('motivo_perdida'), 'motivo_perdida')
        else:
            validar_texto(datos.get('titulo'), 'titulo')
    return evento


def huella(evento):
    return hashlib.sha256(json.dumps(evento, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def procesado(evento):
    item = tabla('TABLE_RECIBIDOS').get_item(
        Key={k: evento[k] for k in ('tenant_id', 'evento_id')}, ConsistentRead=True).get('Item')
    if item and item['huella'] != huella(evento):
        raise ValueError('evento_id reutilizado con otro contenido')
    return bool(item)


def registro_procesado(evento):
    # Sin TTL: una reentrega tardía conserva la deduplicación.
    return put(os.environ['TABLE_RECIBIDOS'], {
        **{k: evento[k] for k in ('tenant_id', 'evento_id')}, 'huella': huella(evento),
        'tipo': evento['tipo'], 'fecha_procesamiento': ahora()}, 'attribute_not_exists(evento_id)')


def marcar_procesado(evento):
    try:
        cliente.transact_write_items(TransactItems=[registro_procesado(evento)])
    except ClientError as error:
        if not es_condicional(error) or not procesado(evento):
            raise


def plazo(tipo):
    variable, defecto = {
        'oportunidad.ganada': ('DIAS_INICIO_SERVICIO', '1'),
        'cotizacion.enviada': ('DIAS_SEGUIMIENTO_COTIZACION', '3')}[tipo]
    dias = int(os.environ.get(variable, defecto))
    if not 0 <= dias <= 365:
        raise ValueError(f'{variable} debe estar entre 0 y 365')
    return dias


def crear_automatica(evento):
    tenant_id, tipo, datos = evento['tenant_id'], evento['tipo'], evento['datos']
    oportunidad = datos['oportunidad_id']
    estado = control(tenant_id, oportunidad)
    if estado.get('cierre') or estado.get('perdida'):
        marcar_procesado(evento)
        return
    fecha = datetime.fromisoformat(fecha_utc(evento['fecha']).replace('Z', '+00:00'))
    programada = (fecha + timedelta(days=plazo(tipo))).strftime('%Y-%m-%dT%H:%M:%SZ')
    titulos = {'cotizacion.enviada': 'Seguimiento de cotización'}
    responsable = datos['creada_por'] if tipo == 'cotizacion.enviada' else datos['responsable_id']
    actividad_id = 'act_' + hashlib.sha256(f"{tenant_id}|{evento['evento_id']}".encode()).hexdigest()[:32]
    descripcion = f"Generada por {tipo} para {oportunidad}."
    if tipo == 'cotizacion.enviada':
        descripcion += f" Cotización: {datos['cotizacion_id']}."
    item = nueva_actividad(tenant_id, actividad_id, 'tarea', titulos[tipo], descripcion,
        datos['cliente_id'], oportunidad, responsable, programada, 'automatica')
    item['evento_origen_id'] = evento['evento_id']
    item['clase_automatica'] = 'seguimiento_cotizacion'
    try:
        cliente.transact_write_items(TransactItems=[
            put(os.environ['TABLE_ACTIVIDADES'], item, 'attribute_not_exists(actividad_id)'),
            registro_procesado(evento), proteger_oportunidad(tenant_id, oportunidad, impedir_cierre=True)])
    except ClientError as error:
        if not es_condicional(error):
            raise
        if procesado(evento):
            return
        estado = control(tenant_id, oportunidad)
        if estado.get('perdida') or estado.get('cierre'):
            marcar_procesado(evento)
            return
        raise  # Conflicto o estado inesperado: SQS reintentará, no confirmar prematuramente.


def registrar_cancelacion(evento):
    """Cierre, tarea de entrega y trabajo pendiente se registran juntos."""
    tenant_id = evento['tenant_id']
    datos = evento['datos']
    oportunidad = datos['oportunidad_id']
    ganada = evento['tipo'] == 'oportunidad.ganada'
    expresion = 'SET cierre = :cierre, fecha_actualizacion = :fecha, cancelacion_estado = :pendiente, cancelacion_proxima = :fecha'
    valores = {':cierre': 'ganada' if ganada else 'perdida', ':fecha': ahora(), ':pendiente': 'pendiente'}
    if not ganada:
        expresion += ', perdida = :si'
        valores[':si'] = True
    operacion = {'Update': {
        'TableName': os.environ['TABLE_OPORTUNIDADES_CONTROL'],
        'Key': serializar({'tenant_id': tenant_id, 'oportunidad_id': oportunidad}),
        'UpdateExpression': expresion,
        'ConditionExpression': 'attribute_not_exists(cierre) AND attribute_not_exists(perdida)',
        'ExpressionAttributeValues': serializar(valores)}}
    operaciones = [operacion, registro_procesado(evento)]
    if ganada:
        fecha = datetime.fromisoformat(fecha_utc(evento['fecha']).replace('Z', '+00:00'))
        programada = (fecha + timedelta(days=plazo('oportunidad.ganada'))).strftime('%Y-%m-%dT%H:%M:%SZ')
        actividad_id = 'act_' + hashlib.sha256(f"{tenant_id}|{evento['evento_id']}".encode()).hexdigest()[:32]
        item = nueva_actividad(tenant_id, actividad_id, 'tarea', 'Iniciar servicio o entrega',
            f'Generada por oportunidad.ganada para {oportunidad}.', datos['cliente_id'], oportunidad,
            datos['responsable_id'], programada, 'automatica')
        item.update(evento_origen_id=evento['evento_id'], clase_automatica='entrega')
        operaciones.append(put(os.environ['TABLE_ACTIVIDADES'], item, 'attribute_not_exists(actividad_id)'))
    try:
        cliente.transact_write_items(TransactItems=operaciones)
    except ClientError as error:
        if not es_condicional(error):
            raise
        if procesado(evento):
            return
        estado = control(tenant_id, oportunidad)
        if estado.get('cierre') == ('ganada' if ganada else 'perdida') or (not ganada and estado.get('perdida')):
            marcar_procesado(evento)
            return
        raise


def lambda_handler(event, context):
    fallidos = []
    for registro in event.get('Records', []):
        mensaje_id = registro['messageId']
        try:
            evento = leer_evento(registro)
            if procesado(evento):
                continue
            if evento['tipo'] in ('oportunidad.perdida', 'oportunidad.ganada'):
                registrar_cancelacion(evento)
            else:
                crear_automatica(evento)
        except Exception as error:
            registrar_fallo('procesar_evento_actividades', error, mensaje_id)
            fallidos.append({'itemIdentifier': mensaje_id})
    return {'batchItemFailures': fallidos}
