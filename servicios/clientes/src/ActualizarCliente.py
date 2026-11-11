from crm_comun import ahora, validar_texto
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
    actual = table.get_item(Key={'tenant_id': tenant_id, 'cliente_id': cliente_id}).get('Item')
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
