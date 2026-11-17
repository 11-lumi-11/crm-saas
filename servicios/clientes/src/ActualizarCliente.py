from crm_comun import ahora, validar_texto, validar_correo
from crm_comun.eventos import evento_pendiente, serializar
from botocore.exceptions import ClientError
from crm_comun import respuesta, leer_body, claims, manejar_errores, ErrorNegocio, validar_responsable
import boto3
import os

TIPOS = ('empresa', 'persona')
ESTADOS = ('prospecto', 'activo', 'inactivo')
CAMPOS = ('nombre', 'tipo', 'documento', 'correo', 'telefono', 'industria', 'ciudad', 'estado', 'responsable_id')

@manejar_errores
def lambda_handler(event, context):
    identidad = claims(event)
    tenant_id = identidad.get('tenant_id')
    rol = identidad.get('rol')
    cliente_id = (event.get('pathParameters') or {}).get('cliente_id')
    body = leer_body(event)

    table = boto3.resource('dynamodb').Table(os.environ['TABLE_CLIENTES'])
    actual = table.get_item(Key={'tenant_id': tenant_id, 'cliente_id': cliente_id}, ConsistentRead=True).get('Item')
    if not actual or actual.get('eliminado'):
        return respuesta(404, {'codigo': 'no_encontrado', 'mensaje': 'El cliente no existe'})

    if 'responsable_id' in body and body['responsable_id'] != actual.get('responsable_id') and rol == 'vendedor':
        return respuesta(403, {'codigo': 'prohibido', 'mensaje': 'Un vendedor no puede reasignar el responsable'})

    if body.get('tipo') is not None and body['tipo'] not in TIPOS:
        return respuesta(400, {'codigo': 'tipo_invalido', 'mensaje': 'Tipo no permitido'})

    if body.get('estado') is not None and body['estado'] not in ESTADOS:
        return respuesta(400, {'codigo': 'estado_invalido', 'mensaje': 'Estado no permitido'})

    if 'responsable_id' in body:
        validar_responsable(body['responsable_id'])
    if 'nombre' in body:
        validar_texto(body['nombre'], 'nombre')
    for campo in ('documento', 'correo', 'telefono', 'industria', 'ciudad'):
        if campo in body and not isinstance(body[campo], str):
            raise ErrorNegocio(400, 'datos_invalidos', f'{campo} debe ser texto')
    if 'correo' in body:
        body['correo'] = validar_correo(body['correo']) if body['correo'].strip() else ''
    cambios, valores, nombres = [], {}, {}
    for campo in CAMPOS:
        if campo not in body or body[campo] is None:
            continue
        valor = body[campo]
        if campo == 'nombre':
            valor = validar_texto(valor, 'nombre')
        if campo == 'correo':
            valor = str(valor).strip().lower()
        alias = f'#c_{campo}'
        cambios.append(f'{alias} = :{campo}')
        valores[f':{campo}'] = valor
        nombres[alias] = campo

    if not cambios:
        return respuesta(400, {'codigo': 'datos_incompletos', 'mensaje': 'Indique al menos un campo para actualizar'})

    cambios.append('fecha_actualizacion = :fecha')
    valores[':fecha'] = ahora()

    if 'correo' in body:
        revision = actual.get('revision_correo', 0)
        cambios.append('revision_correo = :revision_nueva')
        valores[':revision_nueva'] = revision + 1
        valores[':revision_anterior'] = revision
        condicion = 'attribute_exists(cliente_id) AND attribute_not_exists(fecha_eliminacion) AND '
        condicion += '(revision_correo = :revision_anterior OR attribute_not_exists(revision_correo))'
        operacion = {'Update': {'TableName': os.environ['TABLE_CLIENTES'],
            'Key': serializar({'tenant_id': tenant_id, 'cliente_id': cliente_id}),
            'UpdateExpression': 'SET ' + ', '.join(cambios), 'ConditionExpression': condicion,
            'ExpressionAttributeValues': serializar(valores), 'ExpressionAttributeNames': nombres}}
        try:
            boto3.client('dynamodb').transact_write_items(TransactItems=[operacion,
                evento_pendiente('cliente.correo_actualizado', tenant_id,
                    {'cliente_id': cliente_id, 'correo': body['correo'].strip().lower(), 'revision': revision + 1})])
        except ClientError as error:
            razones = error.response.get('CancellationReasons', [])
            if error.response['Error']['Code'] == 'TransactionCanceledException' and razones and razones[0].get('Code') == 'ConditionalCheckFailed':
                raise ErrorNegocio(409, 'conflicto_cliente', 'El cliente cambió; vuelva a intentar')
            raise
        response = table.get_item(Key={'tenant_id': tenant_id, 'cliente_id': cliente_id}, ConsistentRead=True)
        return respuesta(200, {'mensaje': 'Cliente actualizado correctamente', 'cliente': response['Item']})

    try:
        response = table.update_item(
            Key={'tenant_id': tenant_id, 'cliente_id': cliente_id},
            UpdateExpression='SET ' + ', '.join(cambios),
            ExpressionAttributeValues=valores,
            ExpressionAttributeNames=nombres,
            ConditionExpression='attribute_exists(cliente_id) AND attribute_not_exists(fecha_eliminacion)',
            ReturnValues='ALL_NEW'
        )
    except ClientError as error:
        if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise ErrorNegocio(404, 'no_encontrado', 'El cliente no existe')
        raise

    return respuesta(200, {
        'mensaje': 'Cliente actualizado correctamente',
        'cliente': response['Attributes']
    })
