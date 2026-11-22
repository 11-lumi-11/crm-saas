import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'datos'))
sys.path.insert(0, str(ROOT / 'compartido/capa_comun/python'))
spec = importlib.util.spec_from_file_location('cargar_ficticios', ROOT / 'datos/cargar_datos.py')
modulo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modulo)


class CargaDatos(unittest.TestCase):
    def test_escritura_condicional_sin_lambdas(self):
        cliente = MagicMock()
        modulo.escribir_lote(cliente, 'dev-t_clientes', [{'tenant_id': 'ten_demo', 'cliente_id': 'cli_1'}], ('tenant_id', 'cliente_id'))
        put = cliente.transact_write_items.call_args.kwargs['TransactItems'][0]['Put']
        self.assertEqual(put['ConditionExpression'], 'attribute_not_exists(#pk)')
        self.assertEqual(put['ExpressionAttributeNames']['#pk'], 'tenant_id')

    def test_colision_nunca_sobrescribe(self):
        cliente = MagicMock()
        cliente.transact_write_items.side_effect = ClientError({'Error': {'Code': 'TransactionCanceledException'},
            'CancellationReasons': [{'Code': 'ConditionalCheckFailed'}]}, 'TransactWriteItems')
        cliente.batch_get_item.return_value = {'Responses': {'dev-t_clientes': [modulo.serializar({'tenant_id': 'ten_demo', 'cliente_id': 'cli_1', 'nombre': 'Existente'})]}}
        with self.assertRaisesRegex(ValueError, 'Colisión'):
            modulo.escribir_lote(cliente, 'dev-t_clientes', [{'tenant_id': 'ten_demo', 'cliente_id': 'cli_1', 'nombre': 'Nuevo'}], ('tenant_id', 'cliente_id'))
        self.assertEqual(cliente.transact_write_items.call_count, 1)

    def test_reintento_identico_no_vuelve_a_escribir(self):
        cliente = MagicMock()
        item = {'tenant_id': 'ten_demo', 'cliente_id': 'cli_1'}
        cliente.transact_write_items.side_effect = ClientError({'Error': {'Code': 'TransactionCanceledException'},
            'CancellationReasons': [{'Code': 'ConditionalCheckFailed'}]}, 'TransactWriteItems')
        cliente.batch_get_item.return_value = {'Responses': {'dev-t_clientes': [modulo.serializar(item)]}}
        modulo.escribir_lote(cliente, 'dev-t_clientes', [item], ('tenant_id', 'cliente_id'))
        self.assertEqual(cliente.transact_write_items.call_count, 1)

    def test_nombre_de_tenant_ajeno_se_detecta_antes_de_cargar(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp) / 'usuarios/importaciones/t_tenants'
            carpeta.mkdir(parents=True)
            (carpeta / 'parte_0001.jsonl').write_text(
                '{"nombre_normalizado":"empresa a","tenant_id":"ten_a"}\n'
                '{"nombre_normalizado":"empresa b","tenant_id":"ten_b"}\n'
                '{"nombre_normalizado":"empresa c","tenant_id":"ten_c"}\n')
            cliente = MagicMock()
            cliente.scan.return_value = {'Items': [modulo.serializar({'nombre_normalizado': 'empresa a', 'tenant_id': 'ten_ajeno'})]}
            with self.assertRaisesRegex(ValueError, 'pertenece a otra empresa'):
                modulo.verificar_tenants(cliente, 'dev', Path(tmp))
            cliente.transact_write_items.assert_not_called()
