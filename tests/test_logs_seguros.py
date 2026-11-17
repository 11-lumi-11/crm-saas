"""Los registros describen fallos sin incluir datos de la petición."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'compartido/capa_comun/python'))
from crm_comun import ErrorNegocio, manejar_errores, registrar_fallo, registrar_excepciones, respuesta


class LogsSeguros(unittest.TestCase):
    def test_error_validacion_se_registra_sin_body(self):
        @manejar_errores
        def handler(event, context):
            raise ErrorNegocio(400, 'datos_incompletos', 'Falta el título de la oportunidad')
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            resultado = handler({'body': '{"contrasena":"secreto123"}'}, None)
        registro = json.loads(salida.getvalue())
        self.assertEqual(resultado['statusCode'], 400)
        self.assertEqual(registro['motivo'], 'Falta el título de la oportunidad')
        self.assertNotIn('secreto123', salida.getvalue())

    def test_respuesta_error_directa_tambien_se_registra(self):
        @manejar_errores
        def handler(event, context):
            return respuesta(400, {'codigo': 'tipo_invalido', 'mensaje': 'Tipo no permitido'})
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            handler({}, None)
        self.assertEqual(json.loads(salida.getvalue())['codigo'], 'tipo_invalido')

    def test_excepcion_con_datos_privados_no_se_imprime(self):
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            registrar_fallo('procesar_evento', ValueError('token=secreto123'), 'msg-1')
        self.assertNotIn('secreto123', salida.getvalue())
        self.assertEqual(json.loads(salida.getvalue())['tipo_error'], 'ValueError')

    def test_error_programado_no_expone_exception_original(self):
        @registrar_excepciones
        def handler(event, context):
            raise ValueError('correo privado: secreto123')
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida), self.assertRaises(RuntimeError) as error:
            handler({}, None)
        self.assertNotIn('secreto123', salida.getvalue())
        self.assertNotIn('secreto123', str(error.exception))
        self.assertTrue(error.exception.__suppress_context__)


if __name__ == '__main__':
    unittest.main()
