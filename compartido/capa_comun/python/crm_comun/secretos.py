"""Lectura del secreto JWT desde Parameter Store con caché breve por instancia."""
import os
import time

import boto3

_cache = None
_vence = 0.0
_nombre = None


def clave_jwt():
    global _cache, _vence, _nombre
    nombre = os.environ['JWT_SECRET_PARAMETER']
    instante = time.monotonic()
    if _cache is None or _nombre != nombre or instante >= _vence:
        valor = boto3.client('ssm').get_parameter(Name=nombre, WithDecryption=True)['Parameter']['Value']
        if not isinstance(valor, str) or not valor:
            raise ValueError('El parámetro JWT está vacío')
        _cache, _nombre, _vence = valor, nombre, instante + 300
    return _cache
