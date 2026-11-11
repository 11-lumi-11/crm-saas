import json
import hashlib

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


class DatosConFaltantes(dict):
    # Si al evento le falta un campo, el mensaje muestra "-" en lugar de fallar
    def __missing__(self, clave):
        return '-'


def leer_evento(registro):
    # Sin RawMessageDelivery: el body de SQS es el sobre de SNS y el evento va en "Message"
    sobre = json.loads(registro['body'])
    if isinstance(sobre, dict) and 'Message' in sobre:
        return json.loads(sobre['Message'])
    return sobre


def armar_notificaciones(evento):
    tipo = evento.get('tipo')
    tenant_id = evento.get('tenant_id')
    evento_id = evento.get('evento_id')
    if tipo not in PLANTILLAS or not tenant_id or not evento_id:
        print(f'Evento ignorado: tipo={tipo} evento_id={evento_id}')
        return []

    titulo, plantilla, destinos = PLANTILLAS[tipo]
    datos = evento.get('datos') or {}
    mensaje = plantilla.format_map(DatosConFaltantes(datos))
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
            if not isinstance(usuario_id, str) or not usuario_id.startswith('usr_'):
                print(f"Evento {evento_id} sin '{destino}' válido: se omite ese destinatario")
                continue
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
