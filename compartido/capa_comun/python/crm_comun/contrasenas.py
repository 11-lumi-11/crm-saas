"""PBKDF2 con sal por contraseña; compatibilidad de lectura y migración de SHA-256."""
import hashlib
import hmac
import secrets

ITERACIONES = 600_000


def crear_hash(contrasena):
    sal = secrets.token_hex(16)
    resumen = hashlib.pbkdf2_hmac('sha256', contrasena.encode(), bytes.fromhex(sal), ITERACIONES).hex()
    return f'pbkdf2_sha256${ITERACIONES}${sal}${resumen}'


def verificar(contrasena, guardado):
    if not isinstance(guardado, str):
        return False
    if len(guardado) == 64 and all(c in '0123456789abcdef' for c in guardado):
        return hmac.compare_digest(hashlib.sha256(contrasena.encode()).hexdigest(), guardado)
    try:
        algoritmo, iteraciones, sal, resumen = guardado.split('$')
        if algoritmo != 'pbkdf2_sha256' or int(iteraciones) != ITERACIONES:
            return False
        calculado = hashlib.pbkdf2_hmac('sha256', contrasena.encode(), bytes.fromhex(sal), int(iteraciones)).hex()
        return hmac.compare_digest(calculado, resumen)
    except (ValueError, TypeError):
        return False
