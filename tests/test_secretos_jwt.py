import importlib.util
import os
from pathlib import Path
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'compartido/capa_comun/python'))
from crm_comun import secretos

spec = importlib.util.spec_from_file_location('authorizer_secretos', ROOT / 'compartido/authorizer/Authorizer.py')
authorizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(authorizer)


class SecretosJWT(unittest.TestCase):
    def setUp(self):
        secretos._cache, secretos._nombre, secretos._vence = None, None, 0
        self.env = patch.dict(os.environ, {'JWT_SECRET_PARAMETER': '/crm/test/jwt-secret',
                                           'TABLE_USUARIOS': 'usuarios', 'TABLE_TENANTS': 'tenants'})
        self.env.start(); self.addCleanup(self.env.stop)

    def test_cache_y_renovacion(self):
        ssm = MagicMock()
        ssm.get_parameter.return_value = {'Parameter': {'Value': 'secreto'}}
        with patch.object(secretos.boto3, 'client', return_value=ssm), patch.object(secretos.time, 'monotonic', side_effect=[10, 20, 311]):
            self.assertEqual(secretos.clave_jwt(), 'secreto')
            self.assertEqual(secretos.clave_jwt(), 'secreto')
            self.assertEqual(secretos.clave_jwt(), 'secreto')
        self.assertEqual(ssm.get_parameter.call_count, 2)
        ssm.get_parameter.assert_called_with(Name='/crm/test/jwt-secret', WithDecryption=True)

    def test_error_de_parameter_store_no_devuelve_clave_anterior_vencida(self):
        secretos._cache, secretos._nombre, secretos._vence = 'anterior', '/crm/test/jwt-secret', 1
        ssm = MagicMock()
        ssm.get_parameter.side_effect = RuntimeError('no disponible')
        with patch.object(secretos.boto3, 'client', return_value=ssm), patch.object(secretos.time, 'monotonic', return_value=2):
            with self.assertRaises(RuntimeError):
                secretos.clave_jwt()

    def test_authorizer_valida_token_y_rechaza_fallo_de_parameter_store(self):
        secreto = 'clave-de-prueba-con-suficientes-caracteres'
        token = jwt.encode({'tenant_id': 'ten_a', 'usuario_id': 'usr_a', 'rol': 'admin',
                            'exp': datetime.now(timezone.utc) + timedelta(minutes=10)}, secreto, algorithm='HS256')
        tabla = MagicMock()
        tabla.get_item.side_effect = [{'Item': {'estado': 'activo', 'rol': 'admin'}}, {'Item': {'estado': 'activo'}}]
        db = MagicMock(); db.Table.return_value = tabla
        with patch.object(authorizer, 'clave_jwt', return_value=secreto), patch.object(authorizer.boto3, 'resource', return_value=db):
            self.assertTrue(authorizer.lambda_handler({'headers': {'authorization': f'Bearer {token}'}}, None)['isAuthorized'])
        with patch.object(authorizer, 'clave_jwt', side_effect=RuntimeError('sin acceso')):
            self.assertFalse(authorizer.lambda_handler({'headers': {'authorization': f'Bearer {token}'}}, None)['isAuthorized'])


if __name__ == '__main__':
    unittest.main()
