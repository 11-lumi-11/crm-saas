"""SNS/SQS: deduplicación transaccional y barrera persistente ante oportunidades perdidas."""
import hashlib
import json
import os
from datetime import datetime, timedelta

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from crm_comun import ahora, validar_texto, validar_responsable
from crm_comun.eventos import put
from src.utilidades import (tabla, cliente, serializar, validar_id, fecha_utc,
    nueva_actividad, proteger_oportunidad, control, es_condicional)

EVENTOS = ('oportunidad.etapa_cambiada', 'oportunidad.ganada',
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
        if evento['tipo'] == 'oportunidad.etapa_cambiada':
            abiertas = ('nueva', 'calificada', 'propuesta', 'en_negociacion')
            anterior, nueva = datos.get('etapa_anterior'), datos.get('etapa_nueva')
            if anterior not in abiertas or nueva not in abiertas or abiertas.index(nueva) <= abiertas.index(anterior):
                raise ValueError('Cambio entre etapas abiertas inválido')
        elif evento['tipo'] == 'oportunidad.perdida':
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
        'oportunidad.etapa_cambiada': ('DIAS_SEGUIMIENTO_ETAPA', '1'),
        'oportunidad.ganada': ('DIAS_INICIO_SERVICIO', '1'),
        'cotizacion.enviada': ('DIAS_SEGUIMIENTO_COTIZACION', '3')}[tipo]
    dias = int(os.environ.get(variable, defecto))
    if not 0 <= dias <= 365:
        raise ValueError(f'{variable} debe estar entre 0 y 365')
    return dias


def crear_automatica(evento):
    tenant_id, tipo, datos = evento['tenant_id'], evento['tipo'], evento['datos']
    oportunidad = datos['oportunidad_id']
    if control(tenant_id, oportunidad).get('perdida'):
        marcar_procesado(evento)
        return
    fecha = datetime.fromisoformat(fecha_utc(evento['fecha']).replace('Z', '+00:00'))
    programada = (fecha + timedelta(days=plazo(tipo))).strftime('%Y-%m-%dT%H:%M:%SZ')
    titulos = {'oportunidad.etapa_cambiada': 'Seguimiento comercial',
               'oportunidad.ganada': 'Iniciar servicio o entrega',
               'cotizacion.enviada': 'Seguimiento de cotización'}
    responsable = datos['creada_por'] if tipo == 'cotizacion.enviada' else datos['responsable_id']
    actividad_id = 'act_' + hashlib.sha256(f"{tenant_id}|{evento['evento_id']}".encode()).hexdigest()[:32]
    descripcion = f"Generada por {tipo} para {oportunidad}."
    if tipo == 'cotizacion.enviada':
        descripcion += f" Cotización: {datos['cotizacion_id']}."
    item = nueva_actividad(tenant_id, actividad_id, 'tarea', titulos[tipo], descripcion,
        datos['cliente_id'], oportunidad, responsable, programada, 'automatica')
    item['evento_origen_id'] = evento['evento_id']
    try:
        cliente.transact_write_items(TransactItems=[
            put(os.environ['TABLE_ACTIVIDADES'], item, 'attribute_not_exists(actividad_id)'),
            registro_procesado(evento), proteger_oportunidad(tenant_id, oportunidad)])
    except ClientError as error:
        if not es_condicional(error):
            raise
        if procesado(evento):
            return
        if control(tenant_id, oportunidad).get('perdida'):
            marcar_procesado(evento)
            return
        raise  # Conflicto o estado inesperado: SQS reintentará, no confirmar prematuramente.


def cancelar_pendientes(evento, context):
    tenant_id, oportunidad = evento['tenant_id'], evento['datos']['oportunidad_id']
    # Primero barrera durable. Todas las creaciones vinculadas escriben esta misma fila
    # en transacción; después de esta escritura no pueden aparecer nuevas pendientes.
    tabla_control = tabla('TABLE_OPORTUNIDADES_CONTROL')
    resultado_control = tabla_control.update_item(
        Key={'tenant_id': tenant_id, 'oportunidad_id': oportunidad},
        UpdateExpression='SET perdida = :si, fecha_actualizacion = :fecha',
        ExpressionAttributeValues={':si': True, ':fecha': ahora()}, ReturnValues='ALL_NEW')
    consulta = {'KeyConditionExpression': Key('tenant_id').eq(tenant_id), 'ConsistentRead': True,
                'FilterExpression': Attr('oportunidad_id').eq(oportunidad) & Attr('estado').eq('pendiente'),
                'Limit': 100}
    cursor = resultado_control['Attributes'].get('cursor_cancelacion')
    if cursor:
        consulta['ExclusiveStartKey'] = cursor
    # Una lectura fuerte sobre la tabla evita omitir filas por propagación eventual del GSI.
    while True:
        resultado = tabla().query(**consulta)
        for item in resultado.get('Items', []):
            if context and context.get_remaining_time_in_millis() < 5000:
                raise RuntimeError('Cancelación incompleta; reintentar')
            try:
                tabla().update_item(
                    Key={k: item[k] for k in ('tenant_id', 'actividad_id')},
                    UpdateExpression='SET #estado = :cancelada, fecha_actualizacion = :fecha ADD #version :uno',
                    ConditionExpression='#estado = :pendiente',
                    ExpressionAttributeNames={'#estado': 'estado', '#version': 'version'},
                    ExpressionAttributeValues={':pendiente': 'pendiente', ':cancelada': 'cancelada',
                                               ':fecha': ahora(), ':uno': 1})
            except ClientError as error:
                if error.response['Error']['Code'] != 'ConditionalCheckFailedException':
                    raise
        if not resultado.get('LastEvaluatedKey'):
            break
        # Solo guardar progreso tras terminar la página. Un fallo dentro de ella
        # vuelve a recorrerla y las condiciones conservan lo ya completado.
        tabla_control.update_item(
            Key={'tenant_id': tenant_id, 'oportunidad_id': oportunidad},
            UpdateExpression='SET cursor_cancelacion = :cursor',
            ExpressionAttributeValues={':cursor': resultado['LastEvaluatedKey']})
        if context and context.get_remaining_time_in_millis() < 5000:
            raise RuntimeError('Cancelación incompleta; reintentar')
        consulta['ExclusiveStartKey'] = resultado['LastEvaluatedKey']
    # Solo confirmar tras recorrer todo. Si falla a mitad, el siguiente intento continúa
    # cancelando únicamente lo pendiente; jamás modifica completadas/canceladas.
    marcar_procesado(evento)


def lambda_handler(event, context):
    fallidos = []
    for registro in event.get('Records', []):
        mensaje_id = registro['messageId']
        try:
            evento = leer_evento(registro)
            if procesado(evento):
                continue
            if evento['tipo'] == 'oportunidad.perdida':
                cancelar_pendientes(evento, context)
            else:
                crear_automatica(evento)
        except Exception:
            # No registrar datos comerciales, cuerpos o identidades.
            print(f'Mensaje de Actividades pendiente de reintento: {mensaje_id}')
            fallidos.append({'itemIdentifier': mensaje_id})
    return {'batchItemFailures': fallidos}
