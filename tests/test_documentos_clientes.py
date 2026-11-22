import base64
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'compartido/capa_comun/python'))
spec = importlib.util.spec_from_file_location('documentos_clientes', ROOT / 'servicios/clientes/src/Documentos.py')
modulo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modulo)


def evento(tenant='ten_a', cliente='cli_1', documento='doc_1', body=None):
    return {'requestContext': {'authorizer': {'lambda': {'tenant_id': tenant, 'usuario_id': 'usr_1', 'rol': 'vendedor'}}},
            'pathParameters': {'cliente_id': cliente, 'documento_id': documento}, 'body': json.dumps(body or {})}


class DocumentosClientes(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'TABLE_CLIENTES': 'clientes', 'TABLE_DOCUMENTOS': 'documentos', 'BUCKET_DOCUMENTOS': 'bucket'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.clientes, self.documentos, self.s3 = MagicMock(), MagicMock(), MagicMock()
        self.clientes.get_item.return_value = {'Item': {'cliente_id': 'cli_1'}}
        self.db = MagicMock()
        self.db.Table.side_effect = lambda nombre: {'clientes': self.clientes, 'documentos': self.documentos}[nombre]
        self.resource = patch.object(modulo.boto3, 'resource', return_value=self.db)
        self.client = patch.object(modulo.boto3, 'client', return_value=self.s3)
        self.resource.start(); self.client.start()
        self.addCleanup(self.resource.stop); self.addCleanup(self.client.stop)

    def test_subir_guarda_archivo_y_metadatos_del_tenant(self):
        r = modulo.subir(evento(body={'nombre': 'contrato.pdf', 'contenido_base64': base64.b64encode(b'pdf').decode()}), None)
        self.assertEqual(r['statusCode'], 201)
        item = self.documentos.put_item.call_args.kwargs['Item']
        self.assertEqual((item['tenant_id'], item['cliente_id'], item['usuario_id']), ('ten_a', 'cli_1', 'usr_1'))
        self.assertEqual(self.s3.put_object.call_args.kwargs['Body'], b'pdf')
        self.assertNotIn('clave_s3', json.loads(r['body'])['documento'])

    def test_cliente_ajeno_no_permite_subir_ni_descargar(self):
        self.clientes.get_item.return_value = {}
        self.assertEqual(modulo.subir(evento(tenant='ten_otro'), None)['statusCode'], 404)
        self.assertEqual(modulo.descargar(evento(tenant='ten_otro'), None)['statusCode'], 404)
        self.s3.put_object.assert_not_called()
        self.s3.generate_presigned_url.assert_not_called()
        self.assertEqual(self.clientes.get_item.call_args.kwargs['Key']['tenant_id'], 'ten_otro')

    def test_documento_de_otro_cliente_no_se_descarga(self):
        self.documentos.get_item.return_value = {'Item': {'cliente_id': 'cli_ajeno'}}
        self.assertEqual(modulo.descargar(evento(), None)['statusCode'], 404)
        self.s3.generate_presigned_url.assert_not_called()

    def test_descarga_valida_usa_clave_guardada_y_caduca(self):
        self.documentos.get_item.return_value = {'Item': {'cliente_id': 'cli_1', 'clave_s3': 'ten_a/cli_1/doc_1', 'nombre': 'contrato.pdf'}}
        self.s3.generate_presigned_url.return_value = 'https://ejemplo.test/temporal'
        r = modulo.descargar(evento(), None)
        self.assertEqual(r['statusCode'], 200)
        self.assertEqual(self.s3.generate_presigned_url.call_args.kwargs['ExpiresIn'], 60)
        self.assertEqual(self.s3.generate_presigned_url.call_args.kwargs['Params']['Key'], 'ten_a/cli_1/doc_1')

    def test_archivo_invalido_y_fallo_de_registro(self):
        self.assertEqual(modulo.subir(evento(body={'nombre': 'x', 'contenido_base64': '!!'}), None)['statusCode'], 400)
        self.s3.put_object.assert_not_called()
        self.documentos.put_item.side_effect = RuntimeError('fallo')
        self.assertEqual(modulo.subir(evento(body={'nombre': 'x', 'contenido_base64': 'eA=='}), None)['statusCode'], 500)
        self.s3.delete_object.assert_called_once()

    def test_listado_filtra_por_tenant_y_cliente_y_oculta_clave(self):
        self.documentos.query.return_value = {'Items': [{'documento_id': 'doc_1', 'tenant_id': 'ten_a', 'cliente_id': 'cli_1', 'clave_s3': 'privada'}],
                                             'LastEvaluatedKey': {'documento_id': 'doc_1'}}
        r = json.loads(modulo.listar(evento(), None)['body'])
        self.assertEqual(r['siguiente'], 'doc_1')
        self.assertNotIn('clave_s3', r['documentos'][0])
        self.assertEqual(self.documentos.query.call_args.kwargs['IndexName'], 'cliente_id-index')
        condicion = self.documentos.query.call_args.kwargs['KeyConditionExpression'].get_expression()
        valores = [exp.get_expression()['values'][1] for exp in condicion['values']]
        self.assertEqual(valores, ['ten_a', 'cli_1'])


if __name__ == '__main__':
    unittest.main()
