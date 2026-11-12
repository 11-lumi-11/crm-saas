from src.utilidades import (
    ErrorNegocio, manejar_errores, respuesta, leer_body, obtener_claims, generar_id, ahora, tabla,
    exigir_gestion, validar_texto, validar_texto_opcional, validar_precio, validar_moneda,
    validar_estado_producto
)


@manejar_errores
def lambda_handler(event, context):
    tenant_id, _, rol = obtener_claims(event)
    exigir_gestion(rol, 'crear productos')
    body = leer_body(event)

    if body.get('nombre') is None or body.get('precio') is None:
        raise ErrorNegocio(400, 'datos_incompletos', 'Faltan campos obligatorios: nombre y precio')

    fecha = ahora()
    producto_id = generar_id('pro')
    item = {
        'tenant_id': tenant_id,
        'producto_id': producto_id,
        'nombre': validar_texto(body['nombre'], 'nombre'),
        'descripcion': validar_texto_opcional(body.get('descripcion', ''), 'descripcion'),
        'categoria': validar_texto_opcional(body.get('categoria', ''), 'categoria'),
        'precio': validar_precio(body['precio']),
        'moneda': validar_moneda(body['moneda']) if body.get('moneda') is not None else 'PEN',
        'estado': validar_estado_producto(body.get('estado', 'activo')),
        'fecha_creacion': fecha,
        'fecha_actualizacion': fecha
    }

    # El catálogo no publica eventos (no hay ninguno de producto en la sección 8)
    tabla('TABLE_PRODUCTOS').put_item(Item=item, ConditionExpression='attribute_not_exists(producto_id)')
    return respuesta(201, {'mensaje': 'Producto creado exitosamente', 'producto_id': producto_id})
