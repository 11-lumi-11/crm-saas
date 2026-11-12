import os
from botocore.exceptions import ClientError
from crm_comun import ErrorNegocio
from crm_comun.eventos import evento_pendiente, serializar
from src.utilidades import (endpoint, obtener_claims, leer_body, exigir_campos, leer_actividad,
    ahora, cliente, conflicto, comprobar_oportunidad, respuesta, publica)


@endpoint
def lambda_handler(event, context):
    tenant_id, _, _ = obtener_claims(event)
    exigir_campos(leer_body(event), ())
    actividad_id = (event.get('pathParameters') or {}).get('actividad_id')
    actual = leer_actividad(tenant_id, actividad_id)
    if actual['estado'] == 'completada':
        return respuesta(200, {'mensaje': 'La actividad ya estaba completada', 'actividad': publica(actual)})
    if actual['estado'] != 'pendiente':
        raise ErrorNegocio(409, 'actividad_cerrada', 'Una actividad cancelada no puede completarse')
    fecha = ahora()
    operaciones = [{'Update': {
        'TableName': os.environ['TABLE_ACTIVIDADES'],
        'Key': serializar({'tenant_id': tenant_id, 'actividad_id': actividad_id}),
        'UpdateExpression': 'SET #estado = :completada, fecha_actualizacion = :fecha, #version = :nueva',
        'ConditionExpression': '#estado = :pendiente AND #version = :version',
        'ExpressionAttributeNames': {'#estado': 'estado', '#version': 'version'},
        'ExpressionAttributeValues': serializar({':completada': 'completada', ':pendiente': 'pendiente',
            ':fecha': fecha, ':nueva': actual['version'] + 1, ':version': actual['version']})}},
        evento_pendiente('actividad.completada', tenant_id, {
            'actividad_id': actividad_id, 'oportunidad_id': actual.get('oportunidad_id', ''),
            'responsable_id': actual['responsable_id']})]
    oportunidad = actual.get('oportunidad_id')
    if oportunidad:
        operaciones.append(comprobar_oportunidad(tenant_id, oportunidad))
    try:
        cliente.transact_write_items(TransactItems=operaciones)
    except ClientError as error:
        conflicto(error, tenant_id, oportunidad)
    return respuesta(200, {'mensaje': 'Actividad completada', 'actividad': publica({**actual,
        'estado': 'completada', 'fecha_actualizacion': fecha})})
