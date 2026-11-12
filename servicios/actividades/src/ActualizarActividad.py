import os
from botocore.exceptions import ClientError
from crm_comun import ErrorNegocio
from crm_comun.eventos import serializar
from src.utilidades import (endpoint, obtener_claims, leer_body, exigir_campos, leer_actividad,
    validar_responsable, tipo_valido, titulo_valido, descripcion_valida, fecha_utc,
    ahora, cliente, conflicto, comprobar_oportunidad, publica, respuesta)

VALIDADORES = {'tipo': tipo_valido, 'titulo': titulo_valido, 'descripcion': descripcion_valida,
               'responsable_id': validar_responsable, 'fecha_programada': fecha_utc}


@endpoint
def lambda_handler(event, context):
    tenant_id, _, rol = obtener_claims(event)
    actividad_id = (event.get('pathParameters') or {}).get('actividad_id')
    body = leer_body(event)
    exigir_campos(body, (*VALIDADORES, 'estado'))
    actual = leer_actividad(tenant_id, actividad_id)
    if actual['estado'] != 'pendiente':
        raise ErrorNegocio(409, 'actividad_cerrada', 'Solo se editan actividades pendientes')
    if not body:
        raise ErrorNegocio(400, 'datos_incompletos', 'Indique al menos un campo')
    cambios = {campo: validar(body[campo]) for campo, validar in VALIDADORES.items() if campo in body}
    if rol == 'vendedor' and cambios.get('responsable_id', actual['responsable_id']) != actual['responsable_id']:
        raise ErrorNegocio(403, 'prohibido', 'Un vendedor no puede reasignar actividades')
    if 'estado' in body:
        if body['estado'] not in ('pendiente', 'cancelada'):
            raise ErrorNegocio(400, 'estado_invalido', 'Use /completar para completar; solo se permite pendiente o cancelada')
        cambios['estado'] = body['estado']
    cambios.update(fecha_actualizacion=ahora(), version=actual['version'] + 1)
    nombres = {f'#c{i}': campo for i, campo in enumerate(cambios)}
    valores = {f':v{i}': valor for i, valor in enumerate(cambios.values())}
    valores.update({':version': actual['version'], ':pendiente': 'pendiente'})
    operaciones = [{'Update': {
        'TableName': os.environ['TABLE_ACTIVIDADES'],
        'Key': serializar({'tenant_id': tenant_id, 'actividad_id': actividad_id}),
        'UpdateExpression': 'SET ' + ', '.join(f'#c{i} = :v{i}' for i in range(len(cambios))),
        'ConditionExpression': '#estado = :pendiente AND #version = :version',
        'ExpressionAttributeNames': {**nombres, '#estado': 'estado', '#version': 'version'},
        'ExpressionAttributeValues': serializar(valores)}}]
    oportunidad = actual.get('oportunidad_id')
    if oportunidad:
        operaciones.append(comprobar_oportunidad(tenant_id, oportunidad))
    try:
        cliente.transact_write_items(TransactItems=operaciones)
    except ClientError as error:
        conflicto(error, tenant_id, oportunidad)
    return respuesta(200, {'mensaje': 'Actividad actualizada', 'actividad': publica({**actual, **cambios})})
