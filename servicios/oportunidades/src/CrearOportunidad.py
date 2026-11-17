import os

from src.utilidades import (
    ErrorNegocio, manejar_errores, respuesta, leer_body, obtener_claims, generar_id, ahora,
    confirmar, put, validar_texto, validar_monto, validar_moneda,
    validar_fecha_cierre, validar_responsable
)


@manejar_errores
def lambda_handler(event, context):
    tenant_id, usuario_id, rol = obtener_claims(event)
    body = leer_body(event)

    if not tenant_id:
        raise ErrorNegocio(400, 'datos_incompletos', 'Faltan campos obligatorios')
    if body.get('cliente_id') is None:
        raise ErrorNegocio(400, 'datos_incompletos', 'Falta el cliente de la oportunidad')
    if body.get('titulo') is None:
        raise ErrorNegocio(400, 'datos_incompletos', 'Falta el título de la oportunidad')
    if body.get('monto_estimado') is None:
        raise ErrorNegocio(400, 'datos_incompletos', 'Falta el monto de la oportunidad')

    cliente_id = validar_texto(body['cliente_id'], 'cliente_id')
    titulo = validar_texto(body['titulo'], 'titulo')
    monto = validar_monto(body['monto_estimado'])
    moneda = validar_moneda(body['moneda']) if body.get('moneda') is not None else 'PEN'
    if 'probabilidad' in body:
        raise ErrorNegocio(400, 'campo_no_editable', 'La probabilidad ya no se utiliza')

    responsable_id = validar_texto(body['responsable_id'], 'responsable_id') \
        if body.get('responsable_id') is not None else usuario_id
    if responsable_id != usuario_id and rol == 'vendedor':
        raise ErrorNegocio(403, 'prohibido', 'Un vendedor no puede asignar otro responsable')

    responsable_id = validar_responsable(responsable_id)
    fecha = ahora()
    oportunidad_id = generar_id('opo')
    item = {
        'tenant_id': tenant_id,
        'oportunidad_id': oportunidad_id,
        'cliente_id': cliente_id,
        'titulo': titulo,
        'monto_estimado': monto,
        'moneda': moneda,
        'etapa': 'nueva',
        'responsable_id': responsable_id,
        'fecha_creacion': fecha,
        'fecha_actualizacion': fecha
    }
    if body.get('cliente_nombre') is not None:
        item['cliente_nombre'] = validar_texto(body['cliente_nombre'], 'cliente_nombre')
    if body.get('fecha_cierre_estimada') is not None:
        item['fecha_cierre_estimada'] = validar_fecha_cierre(body['fecha_cierre_estimada'])

    confirmar([put(os.environ['TABLE_OPORTUNIDADES'], item, 'attribute_not_exists(oportunidad_id)')],
              'oportunidad.creada', tenant_id, {
        'oportunidad_id': oportunidad_id,
        'cliente_id': cliente_id,
        'titulo': titulo,
        'monto_estimado': monto,
        'responsable_id': responsable_id
    })

    return respuesta(201, {
        'mensaje': 'Oportunidad creada exitosamente',
        'oportunidad_id': oportunidad_id
    })
