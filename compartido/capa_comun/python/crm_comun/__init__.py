"""Contrato HTTP y validaciones comunes a todos los servicios."""
import base64
import binascii
import functools
import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal


class ErrorNegocio(Exception):
    def __init__(self, http, codigo, mensaje):
        super().__init__(mensaje)
        self.http, self.codigo, self.mensaje = http, codigo, mensaje


def convertir_decimal(valor):
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    raise TypeError(f'Tipo no serializable: {type(valor)}')


def respuesta(estado, cuerpo):
    return {'statusCode': estado, 'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(cuerpo, default=convertir_decimal, allow_nan=False)}


MOTIVOS_SEGUROS = frozenset({
    'El body no es un JSON válido', 'El body debe ser un objeto JSON',
    'Faltan campos obligatorios', 'Falta el título de la oportunidad',
    'Falta el cliente de la oportunidad', 'Falta el monto de la oportunidad',
    'Credenciales inválidas', 'correo inválido',
    'Tipo inválido', 'Tipo de evento no admitido', 'Evento no admitido',
    'Cotización inexistente', 'Cliente de la venta no encontrado',
    'Contacto principal no encontrado', 'Destinatarios del cliente aún no registrados',
    'Cambio de correo aún no procesado', 'Contacto principal aún no procesado',
    'Correo de cliente no coincide', 'Correo de contacto no coincide',
    'Identificador inválido', 'Cliente no coincide con la oportunidad',
    'Solicitud repetida con datos distintos o sin decisión recuperable',
})


def registrar_fallo(proceso, error, mensaje_id=None):
    """Registra solo metadatos: nunca incluye el texto arbitrario de la excepción."""
    datos = {'nivel': 'ERROR', 'proceso': proceso, 'tipo_error': type(error).__name__}
    if isinstance(error, (ValueError, ErrorNegocio)) and str(error) in MOTIVOS_SEGUROS:
        datos['motivo'] = str(error)
    if isinstance(mensaje_id, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', mensaje_id):
        datos['mensaje_id'] = mensaje_id
    respuesta_aws = getattr(error, 'response', None)
    detalle_aws = respuesta_aws.get('Error', {}) if isinstance(respuesta_aws, dict) else {}
    codigo = detalle_aws.get('Code') if isinstance(detalle_aws, dict) else None
    if isinstance(codigo, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', codigo):
        datos['codigo_aws'] = codigo
    print(json.dumps(datos, ensure_ascii=False))


def registrar_respuesta_error(proceso, resultado, context):
    try:
        cuerpo = json.loads(resultado.get('body', '{}'))
        codigo = cuerpo.get('codigo', 'error_http')
        if not isinstance(codigo, str) or not re.fullmatch(r'[a-z0-9_]{1,80}', codigo):
            codigo = 'error_http'
        entrada = {'nivel': 'ERROR' if resultado['statusCode'] >= 500 else 'WARN',
                   'proceso': proceso, 'estado_http': resultado['statusCode'], 'codigo': codigo}
        if cuerpo.get('mensaje') in MOTIVOS_SEGUROS:
            entrada['motivo'] = cuerpo['mensaje']
        solicitud = getattr(context, 'aws_request_id', None)
        if isinstance(solicitud, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', solicitud):
            entrada['solicitud_id'] = solicitud
        print(json.dumps(entrada, ensure_ascii=False))
    except (ValueError, TypeError, AttributeError):
        print(json.dumps({'nivel': 'ERROR', 'proceso': proceso, 'codigo': 'error_http'}))


def registrar_excepciones(funcion):
    """Conserva el estado de fallo de Lambda sin exponer la excepción original."""
    @functools.wraps(funcion)
    def envolver(event, context):
        try:
            return funcion(event, context)
        except Exception as error:
            registrar_fallo(funcion.__module__, error)
            raise RuntimeError('Falló el procesamiento; consulte el registro estructurado') from None
    return envolver


def manejar_errores(funcion):
    @functools.wraps(funcion)
    def envolver(event, context):
        try:
            resultado = funcion(event, context)
        except ErrorNegocio as error:
            resultado = respuesta(error.http, {'codigo': error.codigo, 'mensaje': error.mensaje})
        except Exception as error:
            registrar_fallo(funcion.__module__, error)
            return respuesta(500, {'codigo': 'error_interno', 'mensaje': 'No se pudo completar la operación'})
        if isinstance(resultado, dict) and isinstance(resultado.get('statusCode'), int) and resultado['statusCode'] >= 400:
            registrar_respuesta_error(funcion.__module__, resultado, context)
        return resultado
    return envolver


def leer_body(event):
    crudo = event.get('body')
    if crudo is None or crudo == '':
        return {}
    try:
        if event.get('isBase64Encoded'):
            crudo = base64.b64decode(crudo, validate=True).decode('utf-8')
        datos = json.loads(crudo) if isinstance(crudo, str) else crudo
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        raise ErrorNegocio(400, 'json_invalido', 'El body no es un JSON válido')
    if not isinstance(datos, dict):
        raise ErrorNegocio(400, 'json_invalido', 'El body debe ser un objeto JSON')
    return datos


def claims(event):
    datos = event.get('requestContext', {}).get('authorizer', {}).get('lambda', {})
    if not datos.get('tenant_id') or not datos.get('usuario_id') or datos.get('rol') not in ('admin', 'gerente', 'vendedor'):
        raise ErrorNegocio(401, 'no_autorizado', 'Contexto de autenticación inválido')
    return datos


def obtener_claims(event):
    datos = claims(event)
    return datos['tenant_id'], datos['usuario_id'], datos['rol']


def ahora():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def generar_id(prefijo):
    return f'{prefijo}_{uuid.uuid4().hex}'


def validar_texto(valor, campo):
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorNegocio(400, 'datos_invalidos', f'{campo} debe ser texto no vacío')
    return valor.strip()


def validar_responsable(valor):
    if not isinstance(valor, str) or not re.fullmatch(r'usr_[a-zA-Z0-9]+', valor):
        raise ErrorNegocio(400, 'datos_invalidos', 'responsable_id debe tener prefijo usr_ y caracteres alfanuméricos')
    return valor


def validar_correo(valor):
    correo = validar_texto(valor, 'correo').lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', correo):
        raise ErrorNegocio(400, 'datos_invalidos', 'correo inválido')
    return correo
