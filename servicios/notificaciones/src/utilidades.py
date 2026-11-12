import os
import re
import boto3

# Recursos a nivel de módulo (se reutilizan entre invocaciones)
dynamodb = boto3.resource('dynamodb')

PATRON_ID = re.compile(r'not_[a-f0-9]{32}')


def tabla(variable_entorno):
    return dynamodb.Table(os.environ[variable_entorno])


def destino_usuario(tenant_id, usuario_id):
    return f'{tenant_id}#usr#{usuario_id}'


def destino_rol(tenant_id, rol):
    return f'{tenant_id}#rol#{rol}'


def destinos_de(tenant_id, usuario_id, rol):
    # Un usuario ve los avisos dirigidos a él y los dirigidos a su rol
    return (destino_usuario(tenant_id, usuario_id), destino_rol(tenant_id, rol))


def id_lectura(notificacion_id, usuario_id):
    return f'{notificacion_id}#{usuario_id}'
