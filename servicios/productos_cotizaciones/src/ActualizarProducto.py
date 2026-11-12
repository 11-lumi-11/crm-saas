from botocore.exceptions import ClientError

from src.utilidades import (
    ErrorNegocio, manejar_errores, respuesta, leer_body, obtener_claims, ahora, tabla,
    exigir_gestion, validar_texto, validar_texto_opcional, validar_precio, validar_moneda,
    validar_estado_producto
)

# Para desactivar un producto se envía {"estado": "inactivo"}; no hay borrado
VALIDADORES = {
    'nombre': lambda v: validar_texto(v, 'nombre'),
    'descripcion': lambda v: validar_texto_opcional(v, 'descripcion'),
    'categoria': lambda v: validar_texto_opcional(v, 'categoria'),
    'precio': validar_precio,
    'moneda': validar_moneda,
    'estado': validar_estado_producto
}


@manejar_errores
def lambda_handler(event, context):
    tenant_id, _, rol = obtener_claims(event)
    exigir_gestion(rol, 'editar productos')
    producto_id = (event.get('pathParameters') or {}).get('producto_id')
    body = leer_body(event)

    cambios, valores, nombres = [], {}, {}
    for campo, validar in VALIDADORES.items():
        if body.get(campo) is None:
            continue
        cambios.append(f'#c_{campo} = :{campo}')
        valores[f':{campo}'] = validar(body[campo])
        nombres[f'#c_{campo}'] = campo
    if not cambios:
        raise ErrorNegocio(400, 'datos_incompletos', 'Indique al menos un campo para actualizar')

    cambios.append('fecha_actualizacion = :fecha')
    valores[':fecha'] = ahora()
    try:
        resultado = tabla('TABLE_PRODUCTOS').update_item(
            Key={'tenant_id': tenant_id, 'producto_id': producto_id},
            UpdateExpression='SET ' + ', '.join(cambios),
            ExpressionAttributeValues=valores,
            ExpressionAttributeNames=nombres,
            ConditionExpression='attribute_exists(producto_id)',
            ReturnValues='ALL_NEW')
    except ClientError as error:
        if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise ErrorNegocio(404, 'no_encontrado', 'El producto no existe')
        raise

    return respuesta(200, {'mensaje': 'Producto actualizado correctamente', 'producto': resultado['Attributes']})
