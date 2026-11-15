"""Carga masiva S3 → Lambda ImportarDatos → DynamoDB, con AWS simulado (moto).

Las tablas se crean leyendo los `serverless.yml` reales (claves, GSI), así la prueba falla si
los datos generados no calzan con la infraestructura declarada. No contacta AWS.

Requiere: pip install "moto[s3,dynamodb]" boto3 pyyaml
Ejecutar desde la raíz:  python -m unittest tests.test_importar_datos -v
Carga completa (330 mil registros, varios minutos): CARGA_COMPLETA=1 python -m unittest tests.test_importar_datos -v
"""
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

import boto3
import yaml
from moto import mock_aws

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'compartido/capa_comun/python'))
os.environ.update(AWS_DEFAULT_REGION='us-east-1', AWS_ACCESS_KEY_ID='test', AWS_SECRET_ACCESS_KEY='test')
STAGE = 'test'
BUCKET = 'bucket-importaciones-prueba'
SERVICIOS = ['usuarios', 'clientes', 'oportunidades', 'actividades', 'productos_cotizaciones', 'notificaciones']
POR_TENANT = 30_000 // 3 if os.environ.get('CARGA_COMPLETA') else 150


class CargadorCloudFormation(yaml.SafeLoader):
    """Lee YAML con etiquetas de CloudFormation (!Ref, !GetAtt, !Sub...) sin interpretarlas."""


CargadorCloudFormation.add_multi_constructor('!', lambda loader, sufijo, nodo: None)


def leer_serverless(servicio):
    texto = (ROOT / 'servicios' / servicio / 'serverless.yml').read_text(encoding='utf-8')
    config = yaml.load(texto, Loader=CargadorCloudFormation)
    entorno = {k: str(v).replace('${sls:stage}', STAGE) for k, v in config['provider']['environment'].items()}

    def resolver(valor):
        return re.sub(r'\$\{self:provider\.environment\.(\w+)\}', lambda m: entorno[m.group(1)], valor)

    return config, entorno, resolver


def crear_tablas(config, resolver):
    cliente = boto3.client('dynamodb')
    for recurso in config['resources']['Resources'].values():
        if recurso['Type'] != 'AWS::DynamoDB::Table':
            continue
        p = recurso['Properties']
        argumentos = {'TableName': resolver(p['TableName']), 'BillingMode': 'PAY_PER_REQUEST',
                      'AttributeDefinitions': p['AttributeDefinitions'], 'KeySchema': p['KeySchema']}
        if p.get('GlobalSecondaryIndexes'):
            argumentos['GlobalSecondaryIndexes'] = [
                {'IndexName': resolver(g['IndexName']), 'KeySchema': g['KeySchema'],
                 'Projection': g.get('Projection', {'ProjectionType': 'ALL'})}
                for g in p['GlobalSecondaryIndexes']]
        cliente.create_table(**argumentos)


def cargar_handler(servicio):
    for nombre in list(sys.modules):
        if nombre == 'src' or nombre.startswith('src.') or nombre == 'crm_comun.importacion':
            del sys.modules[nombre]
    sys.path.insert(0, str(ROOT / 'servicios' / servicio))
    try:
        return importlib.import_module('src.ImportarDatos')
    finally:
        sys.path.pop(0)


def evento_s3(clave):
    clave_codificada = clave.replace(' ', '+')  # S3 envía la clave codificada para URL
    return {'Records': [{'eventSource': 'aws:s3', 'eventName': 'ObjectCreated:Put',
                         's3': {'bucket': {'name': BUCKET}, 'object': {'key': clave_codificada}}}]}


def contar(nombre_tabla):
    tabla, total, args = boto3.resource('dynamodb').Table(nombre_tabla), 0, {'Select': 'COUNT'}
    while True:
        r = tabla.scan(**args)
        total += r['Count']
        if 'LastEvaluatedKey' not in r:
            return total
        args['ExclusiveStartKey'] = r['LastEvaluatedKey']


class ImportarDatos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporal = tempfile.TemporaryDirectory()
        cls.salida = Path(cls.temporal.name)
        subprocess.run([sys.executable, str(ROOT / 'datos/generar_datos.py'), '--por-tenant', str(POR_TENANT),
                        '--salida', str(cls.salida)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temporal.cleanup()

    def preparar(self, servicio):
        config, entorno, resolver = leer_serverless(servicio)
        # Variables solo durante esta prueba: no deben contaminar las demás suites
        entorno_temporal = mock.patch.dict(os.environ, entorno)
        entorno_temporal.start()
        self.addCleanup(entorno_temporal.stop)
        crear_tablas(config, resolver)
        boto3.client('s3').create_bucket(Bucket=BUCKET)
        return config, entorno, cargar_handler(servicio)

    def subir_e_importar(self, modulo, clave, contenido):
        boto3.client('s3').put_object(Bucket=BUCKET, Key=clave, Body=contenido)
        return modulo.lambda_handler(evento_s3(clave), None)['archivos'][0]

    def test_serverless_declara_bucket_y_funcion(self):
        for servicio in SERVICIOS:
            with self.subTest(servicio=servicio):
                config, _, _ = leer_serverless(servicio)
                self.assertEqual(config['custom']['bucketImportaciones'],
                                 '${self:service}-${sls:stage}-imp-${aws:accountId}')
                funcion = config['functions']['importarDatos']
                self.assertEqual(funcion['handler'], 'src/ImportarDatos.lambda_handler')
                s3 = funcion['events'][0]['s3']
                self.assertEqual(s3['bucket'], '${self:custom.bucketImportaciones}')
                self.assertEqual(s3['rules'], [{'prefix': 'importaciones/'}, {'suffix': '.jsonl'}])
                self.assertTrue((ROOT / 'servicios' / servicio / 'src/ImportarDatos.py').exists())
                # Nombre real más largo posible con una cuenta de 12 dígitos: límite S3 de 63 caracteres
                nombre = f"{config['service']}-dev-imp-123456789012"
                self.assertLessEqual(len(nombre), 63)
                self.assertRegex(nombre, r'^[a-z0-9][a-z0-9-]+$')

    def test_carga_completa_de_cada_servicio(self):
        for servicio in SERVICIOS:
            with self.subTest(servicio=servicio), mock_aws():
                _, entorno, modulo = self.preparar(servicio)
                archivos = sorted((self.salida / servicio / 'importaciones').rglob('*.jsonl'))
                self.assertTrue(archivos)
                esperados = {}
                for archivo in archivos:
                    clave = archivo.relative_to(self.salida / servicio).as_posix()
                    resultado = self.subir_e_importar(modulo, clave, archivo.read_bytes())
                    self.assertEqual(resultado['estado'], 'completado', resultado)
                    lineas = archivo.read_text(encoding='utf-8').count('\n')
                    self.assertEqual(resultado['registros_escritos'], lineas)
                    esperados[resultado['tabla_dynamodb']] = esperados.get(resultado['tabla_dynamodb'], 0) + lineas
                    reporte = boto3.client('s3').get_object(
                        Bucket=BUCKET, Key='resultados/' + clave[len('importaciones/'):-len('.jsonl')] + '.json')
                    self.assertEqual(json.loads(reporte['Body'].read())['estado'], 'completado')
                for tabla, cantidad in esperados.items():
                    self.assertEqual(contar(tabla), cantidad, tabla)

    def test_tipos_y_consultas_por_indice_tras_la_carga(self):
        with mock_aws():
            _, entorno, modulo = self.preparar('usuarios')
            for archivo in sorted((self.salida / 'usuarios/importaciones').rglob('*.jsonl')):
                self.subir_e_importar(modulo, archivo.relative_to(self.salida / 'usuarios').as_posix(), archivo.read_bytes())
            usuarios = boto3.resource('dynamodb').Table(entorno['TABLE_USUARIOS'])
            # El login busca por el GSI correo-index: la cuenta demo debe encontrarse
            marta = usuarios.query(IndexName='correo-index',
                                   KeyConditionExpression=boto3.dynamodb.conditions.Key('correo').eq('marta@seguros.pe'))['Items']
            self.assertEqual(len(marta), 1)
            self.assertEqual(marta[0]['tenant_id'], 'ten_seguros')
            from crm_comun.contrasenas import verificar
            self.assertTrue(verificar('Demo2026!', marta[0]['contrasena_hash']))
        with mock_aws():
            _, entorno, modulo = self.preparar('productos_cotizaciones')
            for archivo in sorted((self.salida / 'productos_cotizaciones/importaciones').rglob('*.jsonl')):
                self.subir_e_importar(modulo, archivo.relative_to(self.salida / 'productos_cotizaciones').as_posix(),
                                      archivo.read_bytes())
            cotizacion = boto3.resource('dynamodb').Table(entorno['TABLE_COTIZACIONES']).query(
                IndexName='estado-index', Limit=1,
                KeyConditionExpression=boto3.dynamodb.conditions.Key('tenant_id').eq('ten_electro')
                & boto3.dynamodb.conditions.Key('estado').eq('aceptada'))['Items'][0]
            # Los montos llegan como Decimal (DynamoDB no acepta float) y los ítems como lista
            self.assertIsInstance(cotizacion['total'], Decimal)
            self.assertIsInstance(cotizacion['items'], list)

    def test_rechaza_tabla_de_otro_servicio(self):
        with mock_aws():
            _, entorno, modulo = self.preparar('oportunidades')
            linea = json.dumps({'tenant_id': 'ten_seguros', 'cliente_id': 'cli_1', 'nombre': 'X'}) + '\n'
            resultado = self.subir_e_importar(modulo, 'importaciones/t_clientes/intruso.jsonl', linea.encode())
            self.assertEqual(resultado['estado'], 'rechazado')
            self.assertIn('no pertenece a este servicio', resultado['motivo'])
            self.assertEqual(contar(entorno['TABLE_OPORTUNIDADES']), 0)

    def test_rechaza_ruta_incorrecta(self):
        with mock_aws():
            _, _, modulo = self.preparar('clientes')
            resultado = self.subir_e_importar(modulo, 'importaciones/t_clientes.jsonl', b'{}\n')
            self.assertEqual(resultado['estado'], 'rechazado')

    def test_lineas_invalidas_se_reportan_y_el_resto_se_carga(self):
        with mock_aws():
            _, entorno, modulo = self.preparar('clientes')
            contenido = '\n'.join([
                json.dumps({'tenant_id': 'ten_seguros', 'cliente_id': 'cli_1', 'nombre': 'Válido', 'monto': 12.5}),
                '{esto no es json',
                json.dumps({'tenant_id': 'ten_seguros', 'nombre': 'Sin clave'}),
                json.dumps({'tenant_id': 'seguros', 'cliente_id': 'cli_2', 'nombre': 'Tenant mal'}),
                '',
                json.dumps({'tenant_id': 'ten_seguros', 'cliente_id': 'cli_3', 'nombre': 'Otro válido'}),
            ]).encode('utf-8')
            resultado = self.subir_e_importar(modulo, 'importaciones/t_clientes/con errores.jsonl', contenido)
            self.assertEqual(resultado['estado'], 'con_errores')
            self.assertEqual((resultado['registros_leidos'], resultado['registros_escritos'],
                              resultado['registros_con_error']), (5, 2, 3))
            self.assertEqual([e['linea'] for e in resultado['errores']], [2, 3, 4])
            self.assertEqual(contar(entorno['TABLE_CLIENTES']), 2)
            item = boto3.resource('dynamodb').Table(entorno['TABLE_CLIENTES']).get_item(
                Key={'tenant_id': 'ten_seguros', 'cliente_id': 'cli_1'})['Item']
            self.assertEqual(item['monto'], Decimal('12.5'))

    def test_reimportar_es_idempotente(self):
        with mock_aws():
            _, entorno, modulo = self.preparar('clientes')
            archivo = next((self.salida / 'clientes/importaciones/t_clientes').glob('*.jsonl'))
            for _ in range(2):  # simula volver a subir el archivo o un reintento automático
                self.subir_e_importar(modulo, 'importaciones/t_clientes/parte_0001.jsonl', archivo.read_bytes())
            self.assertEqual(contar(entorno['TABLE_CLIENTES']), archivo.read_text(encoding='utf-8').count('\n'))


if __name__ == '__main__':
    unittest.main()