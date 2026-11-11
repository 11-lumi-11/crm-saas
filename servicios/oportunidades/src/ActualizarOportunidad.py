from src.utilidades import (
    ErrorNegocio, manejar_errores, respuesta, leer_body, obtener_claims, ahora, tabla, dynamodb,
    leer_oportunidad, validar_texto, validar_monto, validar_probabilidad, validar_moneda,
    validar_fecha_cierre, validar_responsable, ETAPAS_CERRADAS
)

VALIDADORES = {
    'titulo': lambda v: validar_texto(v, 'titulo'),
    'monto_estimado': validar_monto,
    'moneda': validar_moneda,
    'probabilidad': validar_probabilidad,
    'fecha_cierre_estimada': validar_fecha_cierre,
    'responsable_id': validar_responsable,
    'cliente_nombre': lambda v: validar_texto(v, 'cliente_nombre')
}
NO_EDITABLES = ('etapa', 'cliente_id')


@manejar_errores
def lambda_handler(event, context):
    tenant_id, _, rol = obtener_claims(event)
    oportunidad_id = (event.get('pathParameters') or {}).get('oportunidad_id')
    body = leer_body(event)

    actual = leer_oportunidad(tenant_id, oportunidad_id)
    if actual['etapa'] in ETAPAS_CERRADAS:
        raise ErrorNegocio(409, 'oportunidad_cerrada', 'No se puede editar una oportunidad cerrada')

    for campo in NO_EDITABLES:
        if body.get(campo) is not None:
            raise ErrorNegocio(400, 'campo_no_editable', f'{campo} no se puede modificar por esta ruta')

    if 'responsable_id' in body and body['responsable_id'] != actual.get('responsable_id') and rol == 'vendedor':
        raise ErrorNegocio(403, 'prohibido', 'Un vendedor no puede reasignar el responsable')

    cambios, valores, nombres = [], {}, {}
    for campo, validar in VALIDADORES.items():
        if body.get(campo) is None:
            continue
        alias = f'#c_{campo}'
        cambios.append(f'{alias} = :{campo}')
        valores[f':{campo}'] = validar(body[campo])
        nombres[alias] = campo

    if not cambios:
        raise ErrorNegocio(400, 'datos_incompletos', 'Indique al menos un campo para actualizar')

    cambios.append('fecha_actualizacion = :fecha')
    valores[':fecha'] = ahora()
    valores[':ganada'] = 'ganada'
    valores[':perdida'] = 'perdida'
    nombres['#c_etapa'] = 'etapa'

    tabla_oportunidades = tabla('TABLE_OPORTUNIDADES')
    try:
        resultado = tabla_oportunidades.update_item(
            Key={'tenant_id': tenant_id, 'oportunidad_id': oportunidad_id},
            UpdateExpression='SET ' + ', '.join(cambios),
            ExpressionAttributeValues=valores,
            ExpressionAttributeNames=nombres,
            ConditionExpression='attribute_exists(oportunidad_id) AND attribute_not_exists(fecha_eliminacion) AND NOT (#c_etapa IN (:ganada, :perdida))',
            ReturnValues='ALL_NEW'
        )
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        # Pudo borrarse o cerrarse entre la lectura y la escritura
        leer_oportunidad(tenant_id, oportunidad_id)  # 404 si ya no existe
        raise ErrorNegocio(409, 'oportunidad_cerrada', 'No se puede editar una oportunidad cerrada')

    return respuesta(200, {
        'mensaje': 'Oportunidad actualizada correctamente',
        'oportunidad': resultado['Attributes']
    })
