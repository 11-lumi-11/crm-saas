import json
import hashlib
import math
import re
from datetime import datetime
from string import Formatter

from botocore.exceptions import ClientError

from crm_comun import ahora
from src.utilidades import tabla, destino_usuario, destino_rol

# Por tipo de evento: título, mensaje y destinos.
# Un destino es un campo de "datos" con un usuario_id (responsable_id, creada_por, usuario_id)
# o "rol:<rol>" para avisar a todos los usuarios de ese rol en el tenant.
PLANTILLAS = {
    'usuario.creado': (
        'Bienvenido al CRM',
        'Hola {nombre}, tu cuenta con rol {rol} ya está activa.',
        ['usuario_id']),
    'cliente.creado': (
        'Nuevo cliente asignado',
        'Se registró el cliente {nombre} y quedaste como responsable.',
        ['responsable_id']),
    'oportunidad.creada': (
        'Nueva oportunidad',
        'Se creó la oportunidad "{titulo}" por {monto_estimado}.',
        ['responsable_id']),
    'oportunidad.etapa_cambiada': (
        'Oportunidad actualizada',
        'La oportunidad {oportunidad_id} pasó de {etapa_anterior} a {etapa_nueva}.',
        ['responsable_id']),
    'oportunidad.ganada': (
        'Oportunidad ganada',
        'Se ganó la oportunidad "{titulo}" por {monto_estimado}.',
        ['responsable_id', 'rol:gerente']),
    'oportunidad.perdida': (
        'Oportunidad perdida',
        'La oportunidad {oportunidad_id} se perdió. Motivo: {motivo_perdida}.',
        ['responsable_id', 'rol:gerente']),
    'cotizacion.enviada': (
        'Cotización enviada',
        'La cotización {cotizacion_id} por {total} fue enviada al cliente.',
        ['creada_por']),
    'cotizacion.aceptada': (
        'Cotización aceptada',
        'El cliente aceptó la cotización {cotizacion_id} por {total}.',
        ['rol:gerente']),
    'cotizacion.rechazada': (
        'Cotización rechazada',
        'El cliente rechazó la cotización {cotizacion_id}.',
        ['creada_por']),
    'actividad.completada': (
        'Actividad completada',
        'Se completó la actividad {actividad_id}.',
        ['responsable_id']),
}


def leer_evento(registro):
    # Sin RawMessageDelivery: el body de SQS es el sobre de SNS y el evento va en "Message"
    sobre = json.loads(registro['body'])
    if isinstance(sobre, dict) and 'Message' in sobre:
        return json.loads(sobre['Message'])
    return sobre


def armar_notificaciones(evento):
    if not isinstance(evento, dict):
        raise ValueError('El evento debe ser un objeto')
    tipo = evento.get('tipo')
    tenant_id = evento.get('tenant_id')
    evento_id = evento.get('evento_id')
    if not isinstance(tipo, str) or tipo not in PLANTILLAS:
        raise ValueError('Tipo de evento desconocido')
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError('Falta tenant_id')
    if not isinstance(evento_id, str) or not evento_id.strip():
        raise ValueError('Falta evento_id')
    fecha_evento = evento.get('fecha')
    try:
        if not isinstance(fecha_evento, str) or 'T' not in fecha_evento:
            raise ValueError()
        fecha_parseada = datetime.fromisoformat(fecha_evento.replace('Z', '+00:00'))
        if fecha_parseada.tzinfo is None:
            raise ValueError()
    except ValueError:
        raise ValueError('fecha debe ser ISO 8601 con zona horaria')

    titulo, plantilla, destinos = PLANTILLAS[tipo]
    datos = evento.get('datos')
    if not isinstance(datos, dict):
        raise ValueError('datos debe ser un objeto')
    campos = {campo for _, campo, _, _ in Formatter().parse(plantilla) if campo}
    for campo in campos:
        valor = datos.get(campo)
        if campo in ('total', 'monto_estimado'):
            valido = (not isinstance(valor, bool) and isinstance(valor, (int, float))
                      and (not isinstance(valor, float) or math.isfinite(valor)))
        else:
            valido = isinstance(valor, str) and bool(valor.strip())
        if not valido:
            raise ValueError(f'Campo obligatorio inválido: {campo}')
    for destino in destinos:
        if not destino.startswith('rol:'):
            usuario_id = datos.get(destino)
            if not isinstance(usuario_id, str) or not re.fullmatch(r'usr_[A-Za-z0-9]+', usuario_id):
                raise ValueError(f'Destinatario obligatorio inválido: {destino}')
    mensaje = plantilla.format_map(datos)
    fecha = ahora()

    avisos = []
    for destino in destinos:
        item = {'tenant_id': tenant_id, 'tipo': tipo, 'titulo': titulo, 'mensaje': mensaje,
                'evento_id': evento_id, 'fecha_creacion': fecha}
        if destino.startswith('rol:'):
            rol = destino[4:]
            item['rol_destino'] = rol
            item['destino'] = destino_rol(tenant_id, rol)
        else:
            usuario_id = datos.get(destino)
            item['usuario_destino_id'] = usuario_id
            item['destino'] = destino_usuario(tenant_id, usuario_id)

        # Deduplicación: el mismo evento para el mismo destino siempre produce el mismo id
        huella = hashlib.sha256(f"{tenant_id}|{evento_id}|{item['destino']}".encode()).hexdigest()[:32]
        item['notificacion_id'] = f'not_{huella}'
        # Clave de orden única para el GSI: fecha + id (paginación sin empates)
        item['orden'] = f"{fecha}#{item['notificacion_id']}"
        avisos.append(item)
    return avisos


def guardar(aviso):
    try:
        tabla('TABLE_NOTIFICACIONES').put_item(
            Item=aviso, ConditionExpression='attribute_not_exists(notificacion_id)')
        print(f"Aviso guardado: {aviso['notificacion_id']} -> {aviso['destino']}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            # Reentrega del mismo evento: ya existe, no se duplica ni se reinicia
            print(f"Aviso duplicado omitido: {aviso['notificacion_id']}")
        else:
            raise


def lambda_handler(event, context):
    fallidos = []
    for registro in event.get('Records', []):
        mensaje_id = registro['messageId']
        try:
            evento = leer_evento(registro)
            print(f"Evento recibido: tipo={evento.get('tipo')} evento_id={evento.get('evento_id')} tenant={evento.get('tenant_id')}")
            for aviso in armar_notificaciones(evento):
                guardar(aviso)
        except Exception as e:
            # JSON dañado o error de DynamoDB: se reintenta solo este mensaje (3 intentos y luego DLQ)
            print(f'Error en mensaje {mensaje_id}: {e}')
            fallidos.append({'itemIdentifier': mensaje_id})
    return {'batchItemFailures': fallidos}
