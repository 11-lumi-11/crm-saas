"""Retoma cancelaciones por pérdida con lecturas consistentes de Actividades."""
from datetime import datetime, timedelta, timezone
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
from crm_comun import ahora, registrar_fallo, registrar_excepciones
from src.utilidades import tabla


def continuar(trabajo, context):
    tenant = trabajo['tenant_id']
    oportunidad = trabajo['oportunidad_id']
    control = tabla('TABLE_OPORTUNIDADES_CONTROL')
    clave = {'tenant_id': tenant, 'oportunidad_id': oportunidad}
    # El índice solo descubre trabajos. El cursor se lee de la tabla con consistencia fuerte.
    actual = control.get_item(Key=clave, ConsistentRead=True).get('Item', {})
    if actual.get('cancelacion_estado') != 'pendiente':
        return
    consulta = {'KeyConditionExpression': Key('tenant_id').eq(tenant), 'ConsistentRead': True,
                'FilterExpression': Attr('oportunidad_id').eq(oportunidad) & Attr('estado').eq('pendiente'),
                'Limit': 100}
    if actual.get('cierre') == 'ganada':
        consulta['FilterExpression'] &= Attr('clase_automatica').eq('seguimiento_cotizacion')
    if actual.get('cursor_cancelacion'):
        consulta['ExclusiveStartKey'] = actual['cursor_cancelacion']
    actividades = tabla()
    # Varias páginas por ejecución; el cursor se confirma solo al terminar cada página.
    for _ in range(10):
        if context and context.get_remaining_time_in_millis() < 5000:
            return
        pagina = actividades.query(**consulta)
        for item in pagina.get('Items', []):
            if context and context.get_remaining_time_in_millis() < 5000:
                return  # Repetir la página; las actualizaciones son idempotentes.
            try:
                actividades.update_item(
                    Key={k: item[k] for k in ('tenant_id', 'actividad_id')},
                    UpdateExpression='SET #estado = :cancelada, fecha_actualizacion = :fecha ADD #version :uno',
                    ConditionExpression='#estado = :pendiente',
                    ExpressionAttributeNames={'#estado': 'estado', '#version': 'version'},
                    ExpressionAttributeValues={':pendiente': 'pendiente', ':cancelada': 'cancelada',
                                               ':fecha': ahora(), ':uno': 1})
            except ClientError as error:
                if error.response['Error']['Code'] != 'ConditionalCheckFailedException':
                    raise
        cursor = pagina.get('LastEvaluatedKey')
        if not cursor:
            control.update_item(Key=clave,
                UpdateExpression='SET fecha_cancelacion_completa = :fecha REMOVE cancelacion_estado, cancelacion_proxima, cursor_cancelacion',
                ConditionExpression='cancelacion_estado = :pendiente',
                ExpressionAttributeValues={':fecha': ahora(), ':pendiente': 'pendiente'})
            return
        proxima = (datetime.now(timezone.utc) + timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        control.update_item(Key=clave,
            UpdateExpression='SET cursor_cancelacion = :cursor, cancelacion_proxima = :proxima',
            ConditionExpression='cancelacion_estado = :pendiente',
            ExpressionAttributeValues={':cursor': cursor, ':proxima': proxima, ':pendiente': 'pendiente'})
        consulta['ExclusiveStartKey'] = cursor



@registrar_excepciones
def lambda_handler(event, context):
    control = tabla('TABLE_OPORTUNIDADES_CONTROL')
    consulta = {'IndexName': 'cancelaciones-pendientes-index',
                'KeyConditionExpression': Key('cancelacion_estado').eq('pendiente') & Key('cancelacion_proxima').lte(ahora()),
                'Limit': 100}
    errores = 0
    while True:
        pagina = control.query(**consulta)
        for trabajo in pagina.get('Items', []):
            if context and context.get_remaining_time_in_millis() < 5000:
                if errores:
                    raise RuntimeError(f'{errores} cancelaciones pendientes de reintento')
                return {'errores': errores}
            try:
                continuar(trabajo, context)
            except Exception as error:
                errores += 1
                registrar_fallo('continuar_cancelacion_actividades', error)
        if not pagina.get('LastEvaluatedKey'):
            break
        consulta['ExclusiveStartKey'] = pagina['LastEvaluatedKey']
    if errores:
        raise RuntimeError(f'{errores} cancelaciones pendientes de reintento')
    return {'errores': 0}
