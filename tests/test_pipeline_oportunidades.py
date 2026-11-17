"""Reglas del pipeline y orden de eventos, con servicios AWS simulados."""
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'compartido/capa_comun/python'))
os.environ.update(AWS_DEFAULT_REGION='us-east-1', AWS_ACCESS_KEY_ID='test', AWS_SECRET_ACCESS_KEY='test',
    TABLE_ACTIVIDADES='actividades', TABLE_OPORTUNIDADES_CONTROL='control', TABLE_RECIBIDOS='recibidos')


def modulo(servicio, nombre):
    for clave in list(sys.modules):
        if clave == 'src' or clave.startswith('src.'):
            del sys.modules[clave]
    sys.path.insert(0, str(ROOT / 'servicios' / servicio))
    try:
        return importlib.import_module('src.' + nombre)
    finally:
        sys.path.pop(0)


class Pipeline(unittest.TestCase):
    def test_primera_cotizacion_inicia_negociacion(self):
        m = modulo('oportunidades', 'ProcesarCotizacionEnviada')
        evento = {'tipo': 'cotizacion.enviada', 'tenant_id': 'ten_1',
                  'datos': {'oportunidad_id': 'opo_1', 'cliente_id': 'cli_1'}}
        with patch.object(m, 'leer_oportunidad', return_value={'etapa': 'nueva', 'cliente_id': 'cli_1'}), \
             patch.object(m, 'cambiar_etapa') as cambio:
            m.procesar(evento)
        self.assertEqual(cambio.call_args.args[2], 'en_negociacion')

    def test_envio_tardio_no_reabre_oportunidad_ganada(self):
        m = modulo('oportunidades', 'ProcesarCotizacionEnviada')
        evento = {'tipo': 'cotizacion.enviada', 'tenant_id': 'ten_1',
                  'datos': {'oportunidad_id': 'opo_1', 'cliente_id': 'cli_1'}}
        with patch.object(m, 'leer_oportunidad', return_value={'etapa': 'ganada', 'cliente_id': 'cli_1'}), \
             patch.object(m, 'cambiar_etapa') as cambio:
            m.procesar(evento)
        cambio.assert_not_called()

    def test_ganada_registra_barrera_y_tarea_entrega_en_transaccion(self):
        m = modulo('actividades', 'ProcesarEventosActividades')
        evento = {'tipo': 'oportunidad.ganada', 'tenant_id': 'ten_1', 'evento_id': 'evt_1',
                  'fecha': '2026-11-17T12:00:00Z', 'datos': {'oportunidad_id': 'opo_1',
                  'cliente_id': 'cli_1', 'responsable_id': 'usr_1'}}
        cliente = MagicMock()
        with patch.object(m, 'cliente', cliente):
            m.registrar_cancelacion(evento)
        operaciones = cliente.transact_write_items.call_args.kwargs['TransactItems']
        self.assertEqual(len(operaciones), 3)
        self.assertEqual(operaciones[0]['Update']['ExpressionAttributeValues'][':cierre']['S'], 'ganada')
        self.assertEqual(operaciones[2]['Put']['Item']['clase_automatica']['S'], 'entrega')

    def test_envio_tardio_no_crea_seguimiento_tras_ganada(self):
        m = modulo('actividades', 'ProcesarEventosActividades')
        evento = {'tipo': 'cotizacion.enviada', 'tenant_id': 'ten_1', 'datos': {'oportunidad_id': 'opo_1'}}
        with patch.object(m, 'control', return_value={'cierre': 'ganada'}), \
             patch.object(m, 'marcar_procesado') as marcar, patch.object(m, 'cliente') as cliente:
            m.crear_automatica(evento)
        marcar.assert_called_once_with(evento)
        cliente.transact_write_items.assert_not_called()


if __name__ == '__main__':
    unittest.main()
