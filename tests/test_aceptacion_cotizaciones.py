"""Pruebas locales del protocolo de aceptación, sin llamadas a AWS."""
import importlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'compartido/capa_comun/python'))
os.environ.update(AWS_DEFAULT_REGION='us-east-1', AWS_ACCESS_KEY_ID='test',
                  AWS_SECRET_ACCESS_KEY='test', TABLE_OPORTUNIDADES='oportunidades',
                  TABLE_SOLICITUDES='solicitudes', TABLE_EVENTOS='eventos',
                  TABLE_COTIZACIONES='cotizaciones')


def modulo(servicio, nombre):
    for clave in list(sys.modules):
        if clave == 'src' or clave.startswith('src.'):
            del sys.modules[clave]
    sys.path.insert(0, str(ROOT / 'servicios' / servicio))
    try:
        return importlib.import_module('src.' + nombre)
    finally:
        sys.path.pop(0)


class Aceptacion(unittest.TestCase):
    def setUp(self):
        self.datos = {'solicitud_id': 'sol_1', 'cotizacion_id': 'cot_1',
                      'oportunidad_id': 'opo_1', 'cliente_id': 'cli_1'}
        self.evento = {'tipo': 'cotizacion.aceptacion_solicitada', 'tenant_id': 'ten_1', 'datos': self.datos}

    def test_oportunidad_perdida_rechaza_solicitud(self):
        m = modulo('oportunidades', 'ProcesarSolicitudAceptacion')
        tablas = {'solicitudes': MagicMock(), 'oportunidades': MagicMock()}
        tablas['solicitudes'].get_item.return_value = {}
        tablas['oportunidades'].get_item.return_value = {'Item': {'etapa': 'perdida', 'cliente_id': 'cli_1'}}
        cliente = MagicMock()
        with patch.object(m.dynamodb, 'Table', side_effect=lambda nombre: tablas[nombre]), \
             patch.object(m, 'dynamodb_cliente', cliente), patch.object(m, 'cambiar_etapa') as cambio:
            m.procesar(self.evento)
        cambio.assert_not_called()
        operaciones = cliente.transact_write_items.call_args.kwargs['TransactItems']
        sobre = operaciones[-1]['Put']['Item']['evento']['M']
        self.assertEqual(sobre['tipo']['S'], 'oportunidad.aceptacion_rechazada')
        self.assertIn('perdida', sobre['datos']['M']['motivo']['S'])
        self.assertEqual(operaciones[0]['ConditionCheck']['ExpressionAttributeValues'][':etapa']['S'], 'perdida')

    def test_oportunidad_abierta_cierra_y_guarda_decision_juntas(self):
        m = modulo('oportunidades', 'ProcesarSolicitudAceptacion')
        tablas = {'solicitudes': MagicMock(), 'oportunidades': MagicMock()}
        tablas['solicitudes'].get_item.return_value = {}
        tablas['oportunidades'].get_item.return_value = {'Item': {'etapa': 'nueva', 'cliente_id': 'cli_1'}}
        with patch.object(m.dynamodb, 'Table', side_effect=lambda nombre: tablas[nombre]), \
             patch.object(m, 'cambiar_etapa') as cambio:
            m.procesar(self.evento)
        self.assertEqual(cambio.call_args.args[2], 'ganada')
        self.assertEqual(len(cambio.call_args.args[5]), 2)

    def test_solicitud_repetida_no_decide_otra_vez(self):
        m = modulo('oportunidades', 'ProcesarSolicitudAceptacion')
        tabla = MagicMock()
        tabla.get_item.return_value = {'Item': {'resultado': 'confirmada'}}
        with patch.object(m.dynamodb, 'Table', return_value=tabla), patch.object(m, 'cambiar_etapa') as cambio:
            m.procesar(self.evento)
        cambio.assert_not_called()

    def test_resultado_rechazado_deja_mensaje_y_no_publica_aceptacion(self):
        m = modulo('productos_cotizaciones', 'ProcesarResultadoAceptacion')
        tabla = MagicMock()
        tabla.get_item.return_value = {'Item': {'estado': 'aceptacion_pendiente',
                                                'solicitud_aceptacion_id': 'sol_1'}}
        cliente = MagicMock()
        evento = {'tipo': 'oportunidad.aceptacion_rechazada', 'tenant_id': 'ten_1',
                  'datos': {**self.datos, 'motivo': 'Oportunidad perdida'}}
        with patch.object(m, 'tabla', return_value=tabla), patch.object(m, 'dynamodb_cliente', cliente):
            m.procesar(evento)
        operaciones = cliente.transact_write_items.call_args.kwargs['TransactItems']
        self.assertEqual(len(operaciones), 1)
        valores = operaciones[0]['Update']['ExpressionAttributeValues']
        self.assertEqual(valores[':nuevo']['S'], 'enviada')
        self.assertEqual(valores[':motivo']['S'], 'Oportunidad perdida')

    def test_resultado_confirmado_publica_aceptacion(self):
        m = modulo('productos_cotizaciones', 'ProcesarResultadoAceptacion')
        tabla = MagicMock()
        tabla.get_item.return_value = {'Item': {'estado': 'aceptacion_pendiente',
            'solicitud_aceptacion_id': 'sol_1', 'cliente_id': 'cli_1', 'oportunidad_id': 'opo_1', 'total': 5}}
        cliente = MagicMock()
        evento = {'tipo': 'oportunidad.aceptacion_confirmada', 'tenant_id': 'ten_1', 'datos': self.datos}
        with patch.object(m, 'tabla', return_value=tabla), patch.object(m, 'dynamodb_cliente', cliente):
            m.procesar(evento)
        operaciones = cliente.transact_write_items.call_args.kwargs['TransactItems']
        self.assertEqual(operaciones[1]['Put']['Item']['evento']['M']['tipo']['S'], 'cotizacion.aceptada')

    def test_aceptar_devuelve_pendiente_y_solicita_confirmacion(self):
        m = modulo('productos_cotizaciones', 'AceptarCotizacion')
        evento = {'pathParameters': {'cotizacion_id': 'cot_1'}, 'requestContext': {
            'authorizer': {'lambda': {'tenant_id': 'ten_1', 'usuario_id': 'usr_1', 'rol': 'vendedor'}}}}
        cotizacion = {'estado': 'enviada', 'cliente_id': 'cli_1', 'oportunidad_id': 'opo_1'}
        with patch.object(m, 'leer_cotizacion', return_value=cotizacion), \
             patch.object(m, 'esta_vencida', return_value=False), \
             patch.object(m, 'cambiar_estado', return_value='fecha') as cambio:
            respuesta = m.lambda_handler(evento, None)
        self.assertEqual(respuesta['statusCode'], 202)
        self.assertEqual(json.loads(respuesta['body'])['estado'], 'aceptacion_pendiente')
        self.assertEqual(cambio.call_args.args[3:5], ('aceptacion_pendiente', 'cotizacion.aceptacion_solicitada'))

    def test_resultado_repetido_no_publica_otra_vez(self):
        m = modulo('productos_cotizaciones', 'ProcesarResultadoAceptacion')
        tabla = MagicMock()
        tabla.get_item.return_value = {'Item': {'estado': 'aceptada', 'solicitud_aceptacion_id': 'sol_1',
                                                'resultado_solicitud_id': 'sol_1'}}
        cliente = MagicMock()
        evento = {'tipo': 'oportunidad.aceptacion_confirmada', 'tenant_id': 'ten_1', 'datos': self.datos}
        with patch.object(m, 'tabla', return_value=tabla), patch.object(m, 'dynamodb_cliente', cliente):
            m.procesar(evento)
        cliente.transact_write_items.assert_not_called()


if __name__ == '__main__':
    unittest.main()
