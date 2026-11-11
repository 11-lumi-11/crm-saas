from crm_comun import (ErrorNegocio, ahora, generar_id, leer_body, manejar_errores,
                       respuesta, claims, validar_texto, validar_correo)
from crm_comun.contrasenas import crear_hash
from src.Registro import registrar


@manejar_errores
def lambda_handler(event, context):
    identidad = claims(event)
    if identidad['rol'] != 'admin':
        raise ErrorNegocio(403, 'prohibido', 'Solo un admin puede registrar usuarios')
    body = leer_body(event)
    nombre = validar_texto(body.get('nombre'), 'nombre')
    correo = validar_correo(body.get('correo'))
    contrasena = body.get('contrasena')
    validar_texto(contrasena, 'contrasena')
    rol = body.get('rol')
    if rol not in ('admin', 'gerente', 'vendedor'):
        raise ErrorNegocio(400, 'rol_invalido', 'Rol no permitido')
    fecha = ahora()
    usuario = {'tenant_id': identidad['tenant_id'], 'usuario_id': generar_id('usr'),
               'nombre': nombre, 'correo': correo, 'contrasena_hash': crear_hash(contrasena),
               'rol': rol, 'estado': 'activo', 'fecha_creacion': fecha, 'fecha_actualizacion': fecha}
    registrar(usuario)
    return respuesta(201, {'mensaje': 'Usuario creado exitosamente', 'usuario_id': usuario['usuario_id']})
