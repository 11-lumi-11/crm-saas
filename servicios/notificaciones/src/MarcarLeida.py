from botocore.exceptions import ClientError

from crm_comun import ErrorNegocio, manejar_errores, respuesta, obtener_claims, ahora
from src.utilidades import tabla, destinos_de, id_lectura, PATRON_ID


@manejar_errores
def lambda_handler(event, context):
    tenant_id, usuario_id, rol = obtener_claims(event)
    notificacion_id = (event.get('pathParameters') or {}).get('notificacion_id', '')

    no_existe = ErrorNegocio(404, 'no_encontrado', 'La notificación no existe')
    if not PATRON_ID.fullmatch(notificacion_id):
        raise no_existe

    aviso = tabla('TABLE_NOTIFICACIONES').get_item(
        Key={'tenant_id': tenant_id, 'notificacion_id': notificacion_id}).get('Item')
    # Si no está dirigida a este usuario ni a su rol, se responde igual que si no existiera
    if not aviso or aviso.get('destino') not in destinos_de(tenant_id, usuario_id, rol):
        raise no_existe

    # La lectura es individual: un gerente que lee un aviso de rol no lo marca para los demás
    fecha = ahora()
    try:
        tabla('TABLE_LECTURAS').put_item(
            Item={'tenant_id': tenant_id, 'lectura_id': id_lectura(notificacion_id, usuario_id),
                  'notificacion_id': notificacion_id, 'usuario_id': usuario_id, 'fecha_lectura': fecha},
            ConditionExpression='attribute_not_exists(lectura_id)')
    except ClientError as e:
        if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
            raise
        # Ya estaba leída: la operación es idempotente y conserva la primera fecha

    return respuesta(200, {'notificacion_id': notificacion_id, 'leida': True})
