"""Carga masiva de Usuarios y Tenants desde su bucket S3 de importación.

Se dispara con el evento ObjectCreated de S3 sobre importaciones/<tabla>/<archivo>.jsonl.
Solo puede escribir en las tablas propias de este servicio; la lógica está en crm_comun.importacion.
"""
from crm_comun.importacion import crear_handler

# tabla lógica: (variable de entorno con el nombre físico, atributos de la clave primaria)
TABLAS = {
    't_tenants': ('TABLE_TENANTS', ('tenant_id',)),
    't_tenants_locks': ('TABLE_TENANTS_LOCKS', ('nombre_normalizado',)),
    't_usuarios': ('TABLE_USUARIOS', ('tenant_id', 'usuario_id')),
    't_correos_locks': ('TABLE_CORREOS_LOCKS', ('correo',)),
}

lambda_handler = crear_handler(TABLAS)