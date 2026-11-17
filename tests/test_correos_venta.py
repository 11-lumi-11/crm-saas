"""Enrutamiento de avisos de venta con SNS y DynamoDB simulados."""
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'compartido/capa_comun/python'))
os.environ.update(AWS_DEFAULT_REGION='us-east-1', AWS_ACCESS_KEY_ID='test', AWS_SECRET_ACCESS_KEY='test',
                  TABLE_CORREOS_VENTA='correos', STAGE='dev')


def modulo():
    for nombre in list(sys.modules):
        if nombre == 'src' or nombre.startswith('src.'):
            del sys.modules[nombre]
    sys.path.insert(0, str(ROOT / 'servicios/notificaciones'))
    try:
        return importlib.import_module('src.CorreosVenta')
    finally:
        sys.path.pop(0)


class CorreosVenta(unittest.TestCase):
    def test_suscripcion_usa_topic_y_filtro_por_cliente_tenant_y_correo(self):
        m = modulo()
        sns = MagicMock()
        sns.create_topic.return_value = {'TopicArn': 'arn:topic'}
        sns.subscribe.return_value = {'SubscriptionArn': 'arn:subscription'}
        with patch.object(m, 'sns', sns):
            m.suscribir('ten_1', 'cli_1', 'ana@example.com')
        args = sns.subscribe.call_args.kwargs
        self.assertIn(m.filtro('ten_1', 'cli_1', 'ana@example.com'), args['Attributes']['FilterPolicy'])
        self.assertNotEqual(m.filtro('ten_1', 'cli_1', 'ana@example.com'), m.filtro('ten_2', 'cli_1', 'ana@example.com'))

    def test_correo_actualizado_fuera_de_orden_no_revierte_destinatario(self):
        m = modulo()
        t = MagicMock()
        t.get_item.return_value = {'Item': {'cliente_revision': 2, 'cliente': {'correo': 'nuevo@example.com'}}}
        with patch.object(m, 'tabla', return_value=t), patch.object(m, 'suscribir') as suscribir:
            m.actualizar_destinatario({'tipo': 'cliente.correo_actualizado', 'tenant_id': 'ten_1',
                'datos': {'cliente_id': 'cli_1', 'correo': 'anterior@example.com', 'revision': 1}})
        suscribir.assert_not_called()
        t.update_item.assert_not_called()

    def test_venta_mismo_correo_en_ambos_roles_publica_una_vez(self):
        m = modulo()
        destino = {'correo': 'ana@example.com', 'topic_arn': 'arn:ana'}
        t, sns = MagicMock(), MagicMock()
        t.get_item.side_effect = [{'Item': {'cliente_revision': 1, 'cliente': destino,
                                           'principal': {**destino, 'contacto_id': 'con_1'}}}, {}]
        evento = {'evento_id': 'evt_1', 'tenant_id': 'ten_1',
                  'datos': {'cliente_id': 'cli_1', 'cotizacion_id': 'cot_1', 'total': 100, 'moneda': 'PEN',
                            'venta_evento_id': 'evt_original', 'revision_correo': 1,
                            'correo_cliente': 'ana@example.com', 'contacto_id': 'con_1', 'correo_principal': 'ana@example.com'}}
        with patch.object(m, 'tabla', return_value=t), patch.object(m, 'sns', sns):
            m.avisar_venta(evento)
        self.assertEqual(sns.publish.call_count, 1)
        self.assertEqual(sns.publish.call_args.kwargs['TopicArn'], 'arn:ana')

    def test_sin_correo_no_publica(self):
        m = modulo()
        t, sns = MagicMock(), MagicMock()
        t.get_item.return_value = {'Item': {'cliente_revision': 1, 'cliente': {}, 'principal': {}}}
        with patch.object(m, 'tabla', return_value=t), patch.object(m, 'sns', sns):
            m.avisar_venta({'evento_id': 'evt_1', 'tenant_id': 'ten_1',
                'datos': {'cliente_id': 'cli_1', 'cotizacion_id': 'cot_1', 'total': 100,
                          'venta_evento_id': 'evt_original', 'revision_correo': 1,
                          'correo_cliente': '', 'contacto_id': '', 'correo_principal': ''}})
        sns.publish.assert_not_called()

    def test_venta_no_usa_correo_antiguo_cuando_ya_hay_revision_mas_reciente(self):
        m = modulo()
        t, sns = MagicMock(), MagicMock()
        t.get_item.return_value = {'Item': {'cliente_revision': 2,
            'cliente': {'correo': 'nuevo@example.com', 'topic_arn': 'arn:nuevo'}}}
        evento = {'tenant_id': 'ten_1', 'datos': {'cliente_id': 'cli_1', 'cotizacion_id': 'cot_1',
            'total': 100, 'venta_evento_id': 'evt_1', 'revision_correo': 1,
            'correo_cliente': 'antiguo@example.com', 'contacto_id': '', 'correo_principal': ''}}
        with patch.object(m, 'tabla', return_value=t), patch.object(m, 'sns', sns):
            m.avisar_venta(evento)
        sns.publish.assert_not_called()

    def test_venta_espera_evento_de_destinatario_retrasado(self):
        m = modulo()
        t, sns = MagicMock(), MagicMock()
        t.get_item.return_value = {'Item': {'cliente_revision': 1}}
        evento = {'tenant_id': 'ten_1', 'datos': {'cliente_id': 'cli_1', 'cotizacion_id': 'cot_1',
            'total': 100, 'venta_evento_id': 'evt_1', 'revision_correo': 2,
            'correo_cliente': 'nuevo@example.com', 'contacto_id': '', 'correo_principal': ''}}
        with patch.object(m, 'tabla', return_value=t), patch.object(m, 'sns', sns), self.assertRaises(ValueError):
            m.avisar_venta(evento)
        sns.publish.assert_not_called()


if __name__ == '__main__':
    unittest.main()
