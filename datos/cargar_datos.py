"""Carga directa a DynamoDB con inserciones condicionales; no invoca Lambda.

La verificación local debe pasar antes de ejecutar. Cada lote es una transacción:
no se sobrescriben claves existentes, y un reintento admite registros idénticos.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError

from verificar_datos import CLAVES

RAIZ = Path(__file__).resolve().parent
serializer, deserializer = TypeSerializer(), TypeDeserializer()


def serializar(item):
    return {k: serializer.serialize(v) for k, v in item.items()}


def lotes(salida):
    orden = ['usuarios', 'clientes', 'oportunidades', 'productos_cotizaciones', 'actividades', 'notificaciones']
    archivos = list(salida.glob('*/importaciones/*/parte_*.jsonl'))
    for archivo in sorted(archivos, key=lambda p: (orden.index(p.relative_to(salida).parts[0]), str(p))):
        tabla = archivo.parent.name
        if tabla not in CLAVES:
            raise ValueError(f'Tabla no reconocida: {tabla}')
        with archivo.open(encoding='utf-8') as f:
            lote = []
            for linea in f:
                if linea.strip():
                    lote.append(json.loads(linea, parse_float=Decimal))
                if len(lote) == 25:
                    yield tabla, lote
                    lote = []
            if lote:
                yield tabla, lote


def escribir_lote(cliente, tabla, items, claves):
    pendientes = items
    while pendientes:
        operaciones = [{'Put': {'TableName': tabla, 'Item': serializar(item),
                                'ConditionExpression': 'attribute_not_exists(#pk)',
                                'ExpressionAttributeNames': {'#pk': claves[0]}}} for item in pendientes]
        try:
            cliente.transact_write_items(TransactItems=operaciones)
            return
        except ClientError as error:
            if error.response['Error']['Code'] != 'TransactionCanceledException':
                raise
            razones = error.response.get('CancellationReasons', [])
            if not razones or not any(r.get('Code') == 'ConditionalCheckFailed' for r in razones):
                raise
            # La transacción no escribió nada: distinguir reintento idéntico de colisión.
            solicitudes = {tabla: {'Keys': [serializar({k: item[k] for k in claves}) for item in pendientes],
                                    'ConsistentRead': True}}
            existentes = {}
            intentos = 0
            while solicitudes:
                respuesta = cliente.batch_get_item(RequestItems=solicitudes)
                for raw in respuesta.get('Responses', {}).get(tabla, []):
                    registro = {k: deserializer.deserialize(v) for k, v in raw.items()}
                    existentes[tuple(registro[k] for k in claves)] = registro
                solicitudes = respuesta.get('UnprocessedKeys', {})
                if solicitudes:
                    intentos += 1
                    if intentos > 10:
                        raise RuntimeError(f'No se pudieron consultar claves de {tabla}') from None
                    time.sleep(min(0.1 * 2**intentos, 5))
            restantes = []
            for item in pendientes:
                key = {k: item[k] for k in claves}
                existente = existentes.get(tuple(key.values()))
                if existente is None:
                    restantes.append(item)
                elif existente != item:
                    raise ValueError(f'Colisión con datos diferentes en {tabla}: {key}') from None
            if len(restantes) == len(pendientes):
                raise RuntimeError(f'No se pudo resolver conflicto en {tabla}') from None
            pendientes = restantes


def verificar_tenants(cliente, stage, salida):
    registros = []
    for ruta in (salida / 'usuarios/importaciones/t_tenants').glob('parte_*.jsonl'):
        with ruta.open(encoding='utf-8') as archivo:
            registros.extend(json.loads(linea) for linea in archivo if linea.strip())
    esperados = {r['nombre_normalizado']: r['tenant_id'] for r in registros}
    if len(esperados) != 3:
        raise ValueError('Se esperaban tres nombres de tenant diferentes')
    opciones = {'TableName': f'{stage}-t_tenants', 'ConsistentRead': True}
    while True:
        pagina = cliente.scan(**opciones)
        for raw in pagina.get('Items', []):
            item = {k: deserializer.deserialize(v) for k, v in raw.items()}
            nombre = item.get('nombre_normalizado')
            if nombre in esperados and item.get('tenant_id') != esperados[nombre]:
                raise ValueError(f'El nombre de tenant {nombre} pertenece a otra empresa')
        if 'LastEvaluatedKey' not in pagina:
            break
        opciones['ExclusiveStartKey'] = pagina['LastEvaluatedKey']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, default=RAIZ / 'salida')
    parser.add_argument('--stage', default='dev')
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('--cuenta', required=True, help='Cuenta AWS esperada de 12 dígitos')
    parser.add_argument('--ejecutar', action='store_true', help='Escribir en AWS; sin este indicador solo comprueba')
    args = parser.parse_args()
    if len(args.cuenta) != 12 or not args.cuenta.isdigit():
        parser.error('La cuenta debe tener 12 dígitos')
    # El validador retorna código distinto de cero si hay inconsistencias.
    import subprocess
    subprocess.run([sys.executable, str(RAIZ / 'verificar_datos.py'), '--salida', str(args.salida)], check=True)
    sesion = boto3.Session(region_name=args.region)
    cuenta = sesion.client('sts').get_caller_identity()['Account']
    if cuenta != args.cuenta:
        raise RuntimeError('La cuenta AWS no coincide; no se escribió nada')
    cliente = sesion.client('dynamodb')
    for tabla, claves in CLAVES.items():
        fisica = f'{args.stage}-{tabla}'
        descripcion = cliente.describe_table(TableName=fisica)['Table']
        reales = tuple(k['AttributeName'] for k in sorted(descripcion['KeySchema'], key=lambda k: k['KeyType'] != 'HASH'))
        if reales != claves or descripcion['TableStatus'] != 'ACTIVE':
            raise RuntimeError(f'Esquema o estado inesperado en {fisica}: {reales}')
    verificar_tenants(cliente, args.stage, args.salida)
    if not args.ejecutar:
        print('Validación y tablas correctas; no se ha escrito nada.')
        return
    def procesar(lote):
        tabla, registros = lote
        escribir_lote(cliente, f'{args.stage}-{tabla}', registros, CLAVES[tabla])
        return len(registros)

    cantidad = 0
    siguiente_informe = 1000
    # Cuatro trabajos en la computadora, no en Lambda. Las transacciones siguen
    # condicionadas y el búfer limitado evita leer todos los archivos a memoria.
    with ThreadPoolExecutor(max_workers=4) as ejecutor:
        for n in ejecutor.map(procesar, lotes(args.salida), buffersize=8):
            cantidad += n
            if cantidad >= siguiente_informe:
                print(f'{cantidad:,} registros procesados', flush=True)
                siguiente_informe = cantidad + 1000
    print(f'Carga terminada: {cantidad:,} registros procesados.')


if __name__ == '__main__':
    main()
