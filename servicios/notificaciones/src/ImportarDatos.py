"""Carga masiva de Notificaciones desde su bucket S3 de importación.

Se dispara con el evento ObjectCreated de S3 sobre importaciones/<tabla>/<archivo>.jsonl.
Solo puede escribir en las tablas propias de este servicio; la lógica está en crm_comun.importacion.
"""
from crm_comun.importacion import crear_handler

# tabla lógica: (variable de entorno con el nombre físico, atributos de la clave primaria)
TABLAS = {
    't_notificaciones': ('TABLE_NOTIFICACIONES', ('tenant_id', 'notificacion_id')),
    't_lecturas_notificaciones': ('TABLE_LECTURAS', ('tenant_id', 'lectura_id')),
}

lambda_handler = crear_handler(TABLAS)