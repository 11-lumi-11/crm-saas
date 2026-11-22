"""Cuenta registros de cada tabla principal por tenant en DynamoDB."""
import argparse
import boto3
from boto3.dynamodb.conditions import Key

TABLAS = ('t_usuarios', 't_clientes', 't_oportunidades', 't_actividades', 't_cotizaciones', 't_notificaciones')
TENANTS = ('ten_seguros', 'ten_electro', 'ten_consultora')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', default='dev')
    p.add_argument('--region', default='us-east-1')
    p.add_argument('--cuenta', required=True)
    args = p.parse_args()
    sesion = boto3.Session(region_name=args.region)
    if sesion.client('sts').get_caller_identity()['Account'] != args.cuenta:
        raise RuntimeError('La cuenta AWS no coincide')
    db = sesion.resource('dynamodb')
    fallo = False
    for tabla in TABLAS:
        for tenant in TENANTS:
            opciones = {'KeyConditionExpression': Key('tenant_id').eq(tenant), 'Select': 'COUNT', 'ConsistentRead': True}
            total = 0
            while True:
                pagina = db.Table(f'{args.stage}-{tabla}').query(**opciones)
                total += pagina['Count']
                if 'LastEvaluatedKey' not in pagina:
                    break
                opciones['ExclusiveStartKey'] = pagina['LastEvaluatedKey']
            print(f'{tabla} {tenant}: {total:,}', flush=True)
            fallo |= total < 10_000
    if fallo:
        raise SystemExit('Faltan registros en al menos una tabla y tenant')


if __name__ == '__main__':
    main()
