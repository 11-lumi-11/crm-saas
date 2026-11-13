"""Contratos de eventos y respuesta parcial SQS sin acceso a AWS."""
import importlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'compartido/capa_comun/python'))
os.environ.update(AWS_DEFAULT_REGION='us-east-1', AWS_ACCESS_KEY_ID='test', AWS_SECRET_ACCESS_KEY='test')


def modulo():
    for nombre in list(sys.modules):
        if nombre == 'src' or nombre.startswith('src.'):
            del sys.modules[nombre]
    sys.path.insert(0, str(ROOT / 'servicios/notificaciones'))
    try:
        return importlib.import_module('src.ProcesarEventos')
    finally:
        sys.path.pop(0)


class EventosNotificaciones(unittest.TestCase):
    def setUp(self):
        self.modulo = modulo()
        self.evento = {'tipo': 'cliente.creado', 'evento_id': 'evt_1', 'tenant_id': 'ten_1', 'fecha': '2026-11-12T12:00:00Z',
                       'datos': {'cliente_id': 'cli_1', 'nombre': 'Empresa', 'responsable_id': 'usr_1'}}

    def test_evento_valido_crea_aviso(self):
        avisos = self.modulo.armar_notificaciones(self.evento)
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]['usuario_destino_id'], 'usr_1')
        self.assertEqual(avisos[0]['notificacion_id'], self.modulo.armar_notificaciones(self.evento)[0]['notificacion_id'])

    def test_invalidos_se_reintentan_y_no_bloquean_el_lote(self):
        eventos = [self.evento, {**self.evento, 'evento_id': ''},
                   {**self.evento, 'tipo': 'desconocido'}, {**self.evento, 'fecha': ''},
                   {**self.evento, 'datos': {'nombre': 'Empresa'}},
                   {**self.evento, 'datos': {'responsable_id': 'usr_1'}},
                   {**self.evento, 'datos': {'nombre': 'Empresa', 'responsable_id': 'usr_'}}]
        registros = [{'messageId': str(i), 'body': json.dumps({'Message': json.dumps(e)})}
                     for i, e in enumerate(eventos)]
        with patch.object(self.modulo, 'guardar') as guardar:
            resultado = self.modulo.lambda_handler({'Records': registros}, None)
        self.assertEqual(resultado['batchItemFailures'], [{'itemIdentifier': str(i)} for i in range(1, len(eventos))])
        self.assertEqual(guardar.call_count, 1)

    def test_evento_con_dos_destinos_no_guarda_parcial_si_falta_uno(self):
        evento = {'tipo': 'oportunidad.ganada', 'evento_id': 'evt_2', 'tenant_id': 'ten_1', 'fecha': '2026-11-12T12:00:00Z',
                  'datos': {'titulo': 'Venta', 'monto_estimado': 0}}
        registro = {'messageId': 'm1', 'body': json.dumps({'Message': json.dumps(evento)})}
        with patch.object(self.modulo, 'guardar') as guardar:
            resultado = self.modulo.lambda_handler({'Records': [registro]}, None)
        self.assertEqual(resultado['batchItemFailures'], [{'itemIdentifier': 'm1'}])
        guardar.assert_not_called()

    def test_monto_cero_es_valido_y_texto_no_es_un_monto(self):
        evento = {'tipo': 'oportunidad.ganada', 'evento_id': 'evt_2', 'tenant_id': 'ten_1', 'fecha': '2026-11-12T12:00:00Z',
                  'datos': {'titulo': 'Venta', 'monto_estimado': 0, 'responsable_id': 'usr_1'}}
        self.assertEqual(len(self.modulo.armar_notificaciones(evento)), 2)
        evento['datos']['monto_estimado'] = '100'
        with self.assertRaises(ValueError):
            self.modulo.armar_notificaciones(evento)


if __name__ == '__main__':
    unittest.main()
