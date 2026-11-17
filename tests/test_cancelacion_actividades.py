"""Validación local de la barrera y la continuación de cancelaciones."""
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'compartido/capa_comun/python'))
os.environ.update(AWS_DEFAULT_REGION='us-east-1', AWS_ACCESS_KEY_ID='test', AWS_SECRET_ACCESS_KEY='test',
                  TABLE_OPORTUNIDADES_CONTROL='control', TABLE_RECIBIDOS='recibidos', TABLE_ACTIVIDADES='actividades')


def modulo(nombre):
    for clave in list(sys.modules):
        if clave == 'src' or clave.startswith('src.'):
            del sys.modules[clave]
    sys.path.insert(0, str(ROOT / 'servicios/actividades'))
    try:
        return importlib.import_module('src.' + nombre)
    finally:
        sys.path.pop(0)


class Cancelacion(unittest.TestCase):
    def test_barrera_y_evento_se_registran_en_una_transaccion(self):
        m = modulo('ProcesarEventosActividades')
        evento = {'tenant_id': 'ten_1', 'evento_id': 'evt_1', 'tipo': 'oportunidad.perdida',
                  'datos': {'oportunidad_id': 'opo_1'}}
        cliente = MagicMock()
        with patch.object(m, 'cliente', cliente):
            m.registrar_cancelacion(evento)
        operaciones = cliente.transact_write_items.call_args.kwargs['TransactItems']
        self.assertIn('cancelacion_estado', operaciones[0]['Update']['UpdateExpression'])
        self.assertEqual(operaciones[1]['Put']['Item']['evento_id']['S'], 'evt_1')

    def test_recorre_pagina_vacia_con_cursor_y_completa_siguiente(self):
        m = modulo('ContinuarCancelaciones')
        control, actividades = MagicMock(), MagicMock()
        control.get_item.return_value = {'Item': {'cancelacion_estado': 'pendiente'}}
        cursor = {'tenant_id': 'ten_1', 'actividad_id': 'act_1'}
        actividades.query.side_effect = [{'Items': [], 'LastEvaluatedKey': cursor},
            {'Items': [{'tenant_id': 'ten_1', 'actividad_id': 'act_2'}]}]
        with patch.object(m, 'tabla', side_effect=lambda nombre='TABLE_ACTIVIDADES':
                          control if nombre == 'TABLE_OPORTUNIDADES_CONTROL' else actividades):
            m.continuar({'tenant_id': 'ten_1', 'oportunidad_id': 'opo_1'}, None)
        self.assertTrue(actividades.query.call_args_list[0].kwargs['ConsistentRead'])
        self.assertEqual(actividades.query.call_args_list[1].kwargs['ExclusiveStartKey'], cursor)
        self.assertEqual(actividades.update_item.call_count, 1)
        self.assertIn('REMOVE cancelacion_estado', control.update_item.call_args.kwargs['UpdateExpression'])

    def test_tiempo_agotado_no_avanza_cursor_de_pagina_incompleta(self):
        m = modulo('ContinuarCancelaciones')
        control, actividades = MagicMock(), MagicMock()
        control.get_item.return_value = {'Item': {'cancelacion_estado': 'pendiente'}}
        actividades.query.return_value = {'Items': [{'tenant_id': 'ten_1', 'actividad_id': 'act_1'}]}
        context = MagicMock()
        context.get_remaining_time_in_millis.side_effect = [10000, 1000]
        with patch.object(m, 'tabla', side_effect=lambda nombre='TABLE_ACTIVIDADES':
                          control if nombre == 'TABLE_OPORTUNIDADES_CONTROL' else actividades):
            m.continuar({'tenant_id': 'ten_1', 'oportunidad_id': 'opo_1'}, context)
        control.update_item.assert_not_called()


if __name__ == '__main__':
    unittest.main()
