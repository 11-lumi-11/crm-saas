import os
import boto3
from botocore.exceptions import ClientError
from crm_comun import respuesta, leer_body, claims, manejar_errores, ErrorNegocio, ahora
from crm_comun.eventos import serializar


@manejar_errores
def lambda_handler(event, context):
    identidad = claims(event)
    if identidad['rol'] != 'admin':
        raise ErrorNegocio(403, 'prohibido', 'Solo administradores pueden modificar usuarios')
    usuario_id = (event.get('pathParameters') or {}).get('usuario_id')
    body = leer_body(event)
    if usuario_id == identidad['usuario_id'] and (
        body.get('estado', 'activo') != 'activo' or body.get('rol', 'admin') != 'admin'
    ):
        raise ErrorNegocio(409, 'autoproteccion_admin', 'No puede desactivarse ni quitarse su propio rol admin')
    cambios, valores, nombres = [], {}, {}
    for campo, permitidos in [('rol', ('admin', 'gerente', 'vendedor')), ('estado', ('activo', 'inactivo'))]:
        if campo in body:
            if body[campo] not in permitidos:
                raise ErrorNegocio(400, f'{campo}_invalido', f'{campo} no permitido')
            cambios.append(f'#{campo} = :{campo}')
            valores[f':{campo}'] = body[campo]
            nombres[f'#{campo}'] = campo
    if not cambios:
        raise ErrorNegocio(400, 'datos_incompletos', 'Indique rol y/o estado')
    cambios.append('fecha_actualizacion = :fecha')
    valores[':fecha'] = ahora()
    clave = {'tenant_id': identidad['tenant_id'], 'usuario_id': usuario_id}
    operaciones = [{'Update': {
        'TableName': os.environ['TABLE_USUARIOS'], 'Key': serializar(clave),
        'UpdateExpression': 'SET ' + ', '.join(cambios),
        'ExpressionAttributeValues': serializar(valores), 'ExpressionAttributeNames': nombres,
        'ConditionExpression': 'attribute_exists(usuario_id)'}}]
    if usuario_id == identidad['usuario_id']:
        update = operaciones[0]['Update']
        update['ConditionExpression'] += ' AND #actual_rol = :admin_actual AND #actual_estado = :estado_actual'
        update['ExpressionAttributeNames'].update({'#actual_rol': 'rol', '#actual_estado': 'estado'})
        update['ExpressionAttributeValues'].update(serializar({':admin_actual': 'admin', ':estado_actual': 'activo'}))
    else:
        # Impide que dos admins se desactiven mutuamente y dejen al tenant sin admin.
        operaciones.append({'ConditionCheck': {
            'TableName': os.environ['TABLE_USUARIOS'],
            'Key': serializar({'tenant_id': identidad['tenant_id'], 'usuario_id': identidad['usuario_id']}),
            'ConditionExpression': '#rol = :admin AND #estado = :activo',
            'ExpressionAttributeNames': {'#rol': 'rol', '#estado': 'estado'},
            'ExpressionAttributeValues': serializar({':admin': 'admin', ':activo': 'activo'})}})
    try:
        boto3.client('dynamodb').transact_write_items(TransactItems=operaciones)
    except ClientError as error:
        razones = error.response.get('CancellationReasons', [])
        if error.response['Error']['Code'] == 'TransactionCanceledException' and razones:
            if razones[0].get('Code') == 'ConditionalCheckFailed':
                if usuario_id == identidad['usuario_id']:
                    raise ErrorNegocio(403, 'prohibido', 'El administrador ya no está activo')
                raise ErrorNegocio(404, 'no_encontrado', 'El usuario no existe')
            if len(razones) > 1 and razones[1].get('Code') == 'ConditionalCheckFailed':
                raise ErrorNegocio(403, 'prohibido', 'El administrador ya no está activo')
        raise
    usuario = boto3.resource('dynamodb').Table(os.environ['TABLE_USUARIOS']).get_item(
        Key=clave, ConsistentRead=True).get('Item', {})
    usuario.pop('contrasena_hash', None)
    return respuesta(200, {'mensaje': 'Usuario actualizado correctamente', 'usuario': usuario})
