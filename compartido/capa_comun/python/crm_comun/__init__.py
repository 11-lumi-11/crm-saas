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


def manejar_errores(funcion):
    @functools.wraps(funcion)
    def envolver(event, context):
        try:
            return funcion(event, context)
        except ErrorNegocio as error:
            return respuesta(error.http, {'codigo': error.codigo, 'mensaje': error.mensaje})
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
