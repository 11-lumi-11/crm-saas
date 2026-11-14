"""Carga masiva de productos y Cotizaciones desde su bucket S3 de importación.

Se dispara con el evento ObjectCreated de S3 sobre importaciones/<tabla>/<archivo>.jsonl.
Solo puede escribir en las tablas propias de este servicio; la lógica está en crm_comun.importacion.
"""
from crm_comun.importacion import crear_handler

# tabla lógica: (variable de entorno con el nombre físico, atributos de la clave primaria)
TABLAS = {
    't_productos': ('TABLE_PRODUCTOS', ('tenant_id', 'producto_id')),
    't_cotizaciones': ('TABLE_COTIZACIONES', ('tenant_id', 'cotizacion_id')),
}

lambda_handler = crear_handler(TABLAS)