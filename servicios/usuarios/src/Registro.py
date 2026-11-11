"""Registro atómico y candados globales de correo."""
import os
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from crm_comun import ErrorNegocio
from crm_comun.eventos import confirmar, put


def registrar(usuario, tenant=None):
    db = boto3.resource('dynamodb')
    # Compatibilidad con usuarios anteriores a la tabla de candados.
    existentes = db.Table(os.environ['TABLE_USUARIOS']).query(
        IndexName='correo-index', KeyConditionExpression=Key('correo').eq(usuario['correo']), Limit=1)
    if existentes.get('Items'):
        raise ErrorNegocio(409, 'correo_existente', 'El correo ya está registrado')
    operaciones = [put(os.environ['TABLE_CORREOS_LOCKS'],
                      {'correo': usuario['correo'], 'tenant_id': usuario['tenant_id'],
                       'usuario_id': usuario['usuario_id']}, 'attribute_not_exists(correo)'),
                   put(os.environ['TABLE_USUARIOS'], usuario, 'attribute_not_exists(usuario_id)')]
    if tenant:
        existentes = db.Table(os.environ['TABLE_TENANTS']).query(
            IndexName='nombre_normalizado-index',
            KeyConditionExpression=Key('nombre_normalizado').eq(tenant['nombre_normalizado']), Limit=1)
        if existentes.get('Items'):
            raise ErrorNegocio(409, 'empresa_existente', 'La empresa ya está registrada')
        operaciones.extend([
            put(os.environ['TABLE_TENANTS_LOCKS'],
                {'nombre_normalizado': tenant['nombre_normalizado'], 'fecha_creacion': tenant['fecha_creacion']},
                'attribute_not_exists(nombre_normalizado)'),
            put(os.environ['TABLE_TENANTS'], tenant, 'attribute_not_exists(tenant_id)')])
    try:
        confirmar(operaciones, 'usuario.creado', usuario['tenant_id'],
                  {campo: usuario[campo] for campo in ('usuario_id', 'nombre', 'rol')})
    except ClientError as error:
        if error.response['Error']['Code'] == 'TransactionCanceledException':
            razones = error.response.get('CancellationReasons', [])
            if razones and razones[0].get('Code') == 'ConditionalCheckFailed':
                raise ErrorNegocio(409, 'correo_existente', 'El correo ya está registrado')
            if tenant and len(razones) > 2 and razones[2].get('Code') == 'ConditionalCheckFailed':
                raise ErrorNegocio(409, 'empresa_existente', 'La empresa ya está registrada')
        raise
