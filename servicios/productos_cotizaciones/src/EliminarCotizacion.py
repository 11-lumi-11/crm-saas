from botocore.exceptions import ClientError

from src.utilidades import (
    ErrorNegocio, manejar_errores, respuesta, obtener_claims, tabla, ahora, exigir_gestion, leer_cotizacion
)


@manejar_errores
def lambda_handler(event, context):
    tenant_id, _, rol = obtener_claims(event)
    exigir_gestion(rol, 'eliminar cotizaciones')
    cotizacion_id = (event.get('pathParameters') or {}).get('cotizacion_id')
    try:
        # Borrado lógico. Una cotización aceptada ya cerró una venta y se conserva visible
        tabla('TABLE_COTIZACIONES').update_item(
            Key={'tenant_id': tenant_id, 'cotizacion_id': cotizacion_id},
            UpdateExpression='SET eliminado = :si, fecha_eliminacion = :fecha, fecha_actualizacion = :fecha',
            ConditionExpression='attribute_exists(cotizacion_id) AND attribute_not_exists(fecha_eliminacion) '
                                'AND #estado <> :aceptada AND #estado <> :pendiente',
            ExpressionAttributeNames={'#estado': 'estado'},
            ExpressionAttributeValues={':si': True, ':fecha': ahora(), ':aceptada': 'aceptada', ':pendiente': 'aceptacion_pendiente'})
    except ClientError as error:
        if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
            actual = leer_cotizacion(tenant_id, cotizacion_id)  # 404 si no existe o ya está archivada
            if actual['estado'] == 'aceptacion_pendiente':
                raise ErrorNegocio(409, 'aceptacion_pendiente', 'Espere la confirmación antes de archivar la cotización')
            raise ErrorNegocio(409, 'cotizacion_aceptada', 'Una cotización aceptada no se puede eliminar')
        raise
    return respuesta(200, {'mensaje': 'Cotización archivada correctamente', 'cotizacion_id': cotizacion_id})
