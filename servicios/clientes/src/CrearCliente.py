from crm_comun import ahora, generar_id, validar_texto
from crm_comun.eventos import confirmar, put
from crm_comun import respuesta, leer_body, claims, manejar_errores, ErrorNegocio, validar_responsable
import os

TIPOS = ('empresa', 'persona')
ESTADOS = ('prospecto', 'activo', 'inactivo')

@manejar_errores
def lambda_handler(event, context):
    identidad = claims(event)
    tenant_id = identidad.get('tenant_id')
    usuario_id = identidad.get('usuario_id')
    rol = identidad.get('rol')

    body = leer_body(event)
    nombre = body.get('nombre')
    tipo = body.get('tipo')
    estado = body.get('estado', 'prospecto')
    responsable_id = body.get('responsable_id', usuario_id)

    if not tenant_id or not nombre or not tipo:
        return respuesta(400, {'codigo': 'datos_incompletos', 'mensaje': 'Faltan campos obligatorios'})

    if tipo not in TIPOS:
        return respuesta(400, {'codigo': 'tipo_invalido', 'mensaje': 'Tipo no permitido'})

    if estado not in ESTADOS:
        return respuesta(400, {'codigo': 'estado_invalido', 'mensaje': 'Estado no permitido'})

    if responsable_id != usuario_id and rol == 'vendedor':
        return respuesta(403, {'codigo': 'prohibido', 'mensaje': 'Un vendedor no puede asignar otro responsable'})

    responsable_id = validar_responsable(responsable_id)
    nombre = validar_texto(nombre, 'nombre')
    for campo in ('documento', 'correo', 'telefono', 'industria', 'ciudad'):
        if campo in body and not isinstance(body[campo], str):
            raise ErrorNegocio(400, 'datos_invalidos', f'{campo} debe ser texto')

    fecha = ahora()
    cliente_id = generar_id('cli')

    item = {
        'tenant_id': tenant_id,
        'cliente_id': cliente_id,
        'nombre': nombre,
        'tipo': tipo,
        'documento': body.get('documento', ''),
        'correo': (body.get('correo') or '').strip().lower(),
        'telefono': body.get('telefono', ''),
        'industria': body.get('industria', ''),
        'ciudad': body.get('ciudad', ''),
        'estado': estado,
        'responsable_id': responsable_id,
        'fecha_creacion': fecha,
        'fecha_actualizacion': fecha
    }

    confirmar([put(os.environ['TABLE_CLIENTES'], item, 'attribute_not_exists(cliente_id)')],
              'cliente.creado', tenant_id,
              {'cliente_id': cliente_id, 'nombre': nombre, 'responsable_id': responsable_id})

    return respuesta(201, {
        'mensaje': 'Cliente creado exitosamente',
        'cliente_id': cliente_id
    })
