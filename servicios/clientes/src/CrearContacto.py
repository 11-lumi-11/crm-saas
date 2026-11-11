from crm_comun import ahora, generar_id, validar_texto
from botocore.exceptions import ClientError
from crm_comun.eventos import put, serializar
from crm_comun import respuesta, leer_body, claims, manejar_errores, ErrorNegocio
import boto3
import os

@manejar_errores
def lambda_handler(event, context):
    identidad = claims(event)
    tenant_id = identidad.get('tenant_id')
    cliente_id = (event.get('pathParameters') or {}).get('cliente_id')
    body = leer_body(event)
    nombre = body.get('nombre')

    if not tenant_id or not cliente_id or not nombre:
        return respuesta(400, {'codigo': 'datos_incompletos', 'mensaje': 'Faltan campos obligatorios'})

    dynamodb = boto3.resource('dynamodb')
    tabla_clientes = dynamodb.Table(os.environ['TABLE_CLIENTES'])
    cliente = tabla_clientes.get_item(Key={'tenant_id': tenant_id, 'cliente_id': cliente_id}).get('Item')
    if not cliente or cliente.get('eliminado'):
        return respuesta(404, {'codigo': 'no_encontrado', 'mensaje': 'El cliente no existe'})

    fecha = ahora()
    contacto_id = generar_id('con')
    nombre = validar_texto(nombre, 'nombre')
    es_principal = body.get('es_principal', False)
    if not isinstance(es_principal, bool):
        raise ErrorNegocio(400, 'datos_invalidos', 'es_principal debe ser booleano')
    for campo in ('cargo', 'correo', 'telefono'):
        if campo in body and not isinstance(body[campo], str):
            raise ErrorNegocio(400, 'datos_invalidos', f'{campo} debe ser texto')

    item = {
        'tenant_id': tenant_id,
        'contacto_id': contacto_id,
        'cliente_id': cliente_id,
        'nombre': nombre,
        'cargo': body.get('cargo', ''),
        'correo': (body.get('correo') or '').strip().lower(),
        'telefono': body.get('telefono', ''),
        'es_principal': es_principal,
        'fecha_creacion': fecha
    }

    # La fila del cliente actúa como candado y evita carreras con el borrado lógico.
    condicion = 'attribute_exists(cliente_id) AND attribute_not_exists(fecha_eliminacion)'
    operacion = {'TableName': os.environ['TABLE_CLIENTES'],
                 'Key': serializar({'tenant_id': tenant_id, 'cliente_id': cliente_id}),
                 'ConditionExpression': condicion,
                 'UpdateExpression': 'SET fecha_actualizacion = :fecha',
                 'ExpressionAttributeValues': serializar({':fecha': fecha})}
    if es_principal:
        operacion['ConditionExpression'] += ' AND attribute_not_exists(contacto_principal_id)'
        operacion['UpdateExpression'] += ', contacto_principal_id = :contacto'
        operacion['ExpressionAttributeValues'][':contacto'] = {'S': contacto_id}
    try:
        boto3.client('dynamodb').transact_write_items(TransactItems=[
            {'Update': operacion}, put(os.environ['TABLE_CONTACTOS'], item, 'attribute_not_exists(contacto_id)')])
    except ClientError as error:
        razones = error.response.get('CancellationReasons', [])
        if (error.response['Error']['Code'] == 'TransactionCanceledException' and razones
                and razones[0].get('Code') == 'ConditionalCheckFailed'):
            actual = dynamodb.Table(os.environ['TABLE_CLIENTES']).get_item(
                Key={'tenant_id': tenant_id, 'cliente_id': cliente_id}, ConsistentRead=True).get('Item')
            if not actual or actual.get('eliminado'):
                raise ErrorNegocio(404, 'no_encontrado', 'El cliente no existe')
            raise ErrorNegocio(409, 'contacto_principal_existente', 'El cliente ya tiene contacto principal')
        raise

    return respuesta(201, {
        'mensaje': 'Contacto creado exitosamente',
        'contacto_id': contacto_id
    })
