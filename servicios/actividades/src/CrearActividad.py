from botocore.exceptions import ClientError
from crm_comun import ErrorNegocio
from src.utilidades import (endpoint, obtener_claims, leer_body, exigir_campos, validar_id,
    validar_responsable, tipo_valido, titulo_valido, descripcion_valida, fecha_utc,
    generar_id, nueva_actividad, cliente, put, proteger_oportunidad, conflicto, respuesta)
import os


@endpoint
def lambda_handler(event, context):
    tenant_id, usuario_id, rol = obtener_claims(event)
    body = leer_body(event)
    exigir_campos(body, ('tipo', 'titulo', 'descripcion', 'cliente_id', 'oportunidad_id',
                         'responsable_id', 'fecha_programada'))
    responsable = validar_responsable(body.get('responsable_id', usuario_id))
    if rol == 'vendedor' and responsable != usuario_id:
        raise ErrorNegocio(403, 'prohibido', 'Un vendedor solo puede asignarse a sí mismo')
    oportunidad = body.get('oportunidad_id')
    if oportunidad not in (None, ''):
        oportunidad = validar_id(oportunidad, 'oportunidad_id', 'opo')
    item = nueva_actividad(tenant_id, generar_id('act'), tipo_valido(body.get('tipo')),
        titulo_valido(body.get('titulo')), descripcion_valida(body.get('descripcion', '')),
        validar_id(body.get('cliente_id'), 'cliente_id', 'cli'), oportunidad, responsable,
        fecha_utc(body.get('fecha_programada')), 'manual')
    operaciones = [put(os.environ['TABLE_ACTIVIDADES'], item, 'attribute_not_exists(actividad_id)')]
    if oportunidad:
        operaciones.append(proteger_oportunidad(tenant_id, oportunidad))
    try:
        cliente.transact_write_items(TransactItems=operaciones)
    except ClientError as error:
        conflicto(error, tenant_id, oportunidad)
    return respuesta(201, {'mensaje': 'Actividad creada', 'actividad_id': item['actividad_id']})
