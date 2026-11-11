from crm_comun import ahora, generar_id, leer_body, manejar_errores, respuesta, validar_texto, validar_correo
from crm_comun.contrasenas import crear_hash
from src.Registro import registrar


@manejar_errores
def lambda_handler(event, context):
    body = leer_body(event)
    empresa = validar_texto(body.get('nombre_empresa'), 'nombre_empresa')
    nombre = validar_texto(body.get('nombre_admin'), 'nombre_admin')
    correo = validar_correo(body.get('correo'))
    contrasena = body.get('contrasena')
    validar_texto(contrasena, 'contrasena')
    fecha = ahora()
    tenant_id, usuario_id = generar_id('ten'), generar_id('usr')
    tenant = {'tenant_id': tenant_id, 'nombre': empresa,
              'nombre_normalizado': ' '.join(empresa.lower().split()),
              'rubro': validar_texto(body.get('rubro', 'No especificado'), 'rubro'),
              'estado': 'activo', 'fecha_creacion': fecha, 'fecha_actualizacion': fecha}
    usuario = {'tenant_id': tenant_id, 'usuario_id': usuario_id, 'nombre': nombre, 'correo': correo,
               'contrasena_hash': crear_hash(contrasena), 'rol': 'admin', 'estado': 'activo',
               'fecha_creacion': fecha, 'fecha_actualizacion': fecha}
    registrar(usuario, tenant)
    return respuesta(201, {'mensaje': 'Tenant y usuario admin creados exitosamente',
                           'tenant_id': tenant_id, 'usuario_id': usuario_id})
