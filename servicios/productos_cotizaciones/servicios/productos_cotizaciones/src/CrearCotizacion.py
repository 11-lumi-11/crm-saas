from decimal import Decimal, ROUND_HALF_UP

from src.utilidades import (
    ErrorNegocio, manejar_errores, respuesta, leer_body, obtener_claims, generar_id, ahora, tabla,
    validar_id, validar_cantidad, validar_moneda, validar_fecha_vencimiento, vencimiento_por_defecto,
    leer_productos, ITEMS_MAXIMOS, CENTIMOS
)


@manejar_errores
def lambda_handler(event, context):
    tenant_id, usuario_id, _ = obtener_claims(event)
    body = leer_body(event)

    if body.get('oportunidad_id') is None or body.get('cliente_id') is None or body.get('items') is None:
        raise ErrorNegocio(400, 'datos_incompletos', 'Faltan campos obligatorios: oportunidad_id, cliente_id e items')

    # No se consulta Oportunidades ni Clientes (otra base): solo se valida el formato del identificador
    oportunidad_id = validar_id(body['oportunidad_id'], 'oportunidad_id', 'opo')
    cliente_id = validar_id(body['cliente_id'], 'cliente_id', 'cli')
    moneda = validar_moneda(body['moneda']) if body.get('moneda') is not None else 'PEN'
    fecha_vencimiento = validar_fecha_vencimiento(body['fecha_vencimiento']) \
        if body.get('fecha_vencimiento') is not None else vencimiento_por_defecto()

    pedidos = body['items']
    if not isinstance(pedidos, list) or not pedidos:
        raise ErrorNegocio(400, 'datos_invalidos', 'items debe ser una lista no vacía')
    if len(pedidos) > ITEMS_MAXIMOS:
        raise ErrorNegocio(400, 'datos_invalidos', f'Una cotización admite como máximo {ITEMS_MAXIMOS} ítems')

    cantidades = {}
    for pedido in pedidos:
        if not isinstance(pedido, dict) or pedido.get('producto_id') is None or pedido.get('cantidad') is None:
            raise ErrorNegocio(400, 'datos_invalidos', 'Cada ítem necesita producto_id y cantidad')
        producto_id = validar_id(pedido['producto_id'], 'producto_id', 'pro')
        if producto_id in cantidades:
            raise ErrorNegocio(400, 'datos_invalidos', f'{producto_id} está repetido; sume las cantidades en un ítem')
        cantidades[producto_id] = validar_cantidad(pedido['cantidad'])

    # Los productos son de este mismo servicio, así que sí se leen de su tabla
    catalogo = leer_productos(tenant_id, cantidades.keys())
    items, total = [], Decimal('0')
    for producto_id, cantidad in cantidades.items():
        producto = catalogo.get(producto_id)
        if not producto or producto.get('estado') != 'activo':
            raise ErrorNegocio(400, 'producto_no_disponible', f'{producto_id} no existe o está inactivo')
        if producto['moneda'] != moneda:
            raise ErrorNegocio(400, 'moneda_incompatible',
                               f'{producto_id} tiene precio en {producto["moneda"]} y la cotización es en {moneda}')
        subtotal = (producto['precio'] * cantidad).quantize(CENTIMOS, ROUND_HALF_UP)
        total += subtotal
        # Copia de nombre y precio: cambios futuros del catálogo no alteran la cotización
        items.append({
            'producto_id': producto_id,
            'nombre_producto': producto['nombre'],
            'cantidad': cantidad,
            'precio_unitario': producto['precio'],
            'subtotal': subtotal
        })

    fecha = ahora()
    cotizacion_id = generar_id('cot')
    item = {
        'tenant_id': tenant_id,
        'cotizacion_id': cotizacion_id,
        'oportunidad_id': oportunidad_id,
        'cliente_id': cliente_id,
        'estado': 'borrador',
        'items': items,
        'total': total.quantize(CENTIMOS, ROUND_HALF_UP),
        'moneda': moneda,
        'fecha_vencimiento': fecha_vencimiento,
        'creada_por': usuario_id,
        'fecha_creacion': fecha,
        'fecha_actualizacion': fecha
    }
    # Un borrador no publica evento: el catálogo de la sección 8 empieza en cotizacion.enviada
    tabla('TABLE_COTIZACIONES').put_item(Item=item, ConditionExpression='attribute_not_exists(cotizacion_id)')

    return respuesta(201, {
        'mensaje': 'Cotización creada en borrador',
        'cotizacion_id': cotizacion_id,
        'total': item['total'],
        'moneda': moneda
    })
