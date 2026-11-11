"""Preparación de datos previos. Ejecutar con escrituras pausadas; por defecto solo audita.

python datos/migrar_integridad.py --stage dev [--aplicar]
No cambia contraseñas: Login migra SHA-256 a PBKDF2 tras autenticación exitosa.
"""
import argparse
import boto3


def recorrer(tabla):
    consulta = {'ConsistentRead': True}
    while True:
        pagina = tabla.scan(**consulta)
        yield from pagina.get('Items', [])
        if not pagina.get('LastEvaluatedKey'):
            break
        consulta['ExclusiveStartKey'] = pagina['LastEvaluatedKey']


def migrar(stage, aplicar=False):
    db = boto3.resource('dynamodb')
    correos, principales = {}, {}
    for usuario in recorrer(db.Table(f'{stage}-t_usuarios')):
        correo = usuario['correo']
        if correo in correos:
            raise ValueError('Hay correos duplicados; resolverlos antes de continuar')
        correos[correo] = {k: usuario[k] for k in ('tenant_id', 'usuario_id')}
    for contacto in recorrer(db.Table(f'{stage}-t_contactos')):
        if contacto.get('es_principal'):
            clave = (contacto['tenant_id'], contacto['cliente_id'])
            if clave in principales:
                raise ValueError('Hay clientes con varios contactos principales; resolverlos antes de continuar')
            principales[clave] = contacto['contacto_id']
    # Auditar todas las filas antes de escribir. No se imprimen correos ni datos personales.
    locks = db.Table(f'{stage}-t_correos_locks')
    clientes = db.Table(f'{stage}-t_clientes')
    for correo, propietario in correos.items():
        actual = locks.get_item(Key={'correo': correo}, ConsistentRead=True).get('Item')
        if actual and any(actual.get(k) != v for k, v in propietario.items()):
            raise ValueError('Un candado de correo pertenece a otro usuario')
    for (tenant_id, cliente_id), contacto_id in principales.items():
        actual = clientes.get_item(Key={'tenant_id': tenant_id, 'cliente_id': cliente_id}, ConsistentRead=True).get('Item')
        if not actual or actual.get('contacto_principal_id', contacto_id) != contacto_id:
            raise ValueError('Contacto huérfano o candado principal inconsistente')
    if aplicar:
        for correo, propietario in correos.items():
            locks.put_item(Item={'correo': correo, **propietario},
                           ConditionExpression='attribute_not_exists(correo) OR (tenant_id = :tenant AND usuario_id = :usuario)',
                           ExpressionAttributeValues={':tenant': propietario['tenant_id'], ':usuario': propietario['usuario_id']})
        for (tenant_id, cliente_id), contacto_id in principales.items():
            clientes.update_item(Key={'tenant_id': tenant_id, 'cliente_id': cliente_id},
                                 UpdateExpression='SET contacto_principal_id = :contacto',
                                 ConditionExpression='attribute_exists(cliente_id) AND (attribute_not_exists(contacto_principal_id) OR contacto_principal_id = :contacto)',
                                 ExpressionAttributeValues={':contacto': contacto_id})
    return {'correos': len(correos), 'contactos_principales': len(principales), 'aplicado': aplicar}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True)
    parser.add_argument('--aplicar', action='store_true')
    args = parser.parse_args()
    print(migrar(args.stage, args.aplicar))
