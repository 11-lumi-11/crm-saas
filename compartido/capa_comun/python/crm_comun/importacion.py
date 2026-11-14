"""Carga masiva S3 → DynamoDB, dirigida por eventos.

Cada microservicio tiene su propio bucket de importación. Al subir un archivo a
`importaciones/<tabla>/<archivo>.jsonl`, S3 emite el evento ObjectCreated y dispara el Lambda
`ImportarDatos` de ese servicio, que:

1. Comprueba que `<tabla>` sea una tabla propia del servicio (nadie escribe la base de otro).
2. Lee el archivo línea por línea (JSON Lines: un registro JSON por línea).
3. Valida que cada registro traiga su clave primaria y, si aplica, un `tenant_id` válido.
4. Escribe en lotes de 25 con `batch_writer` (máximo de BatchWriteItem), que reintenta solo
   los elementos no procesados.
5. Deja un reporte en `resultados/<tabla>/<archivo>.json` del mismo bucket y en CloudWatch.

La escritura es idempotente: un registro con la misma clave se sobrescribe, así que volver a
subir un archivo, o un reintento automático de S3/Lambda, no duplica datos.
La carga no pasa por el outbox: no publica eventos, para no inundar SNS con datos históricos.
"""
import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import unquote_plus

import boto3

PREFIJO_ENTRADA = 'importaciones/'
PREFIJO_RESULTADOS = 'resultados/'
MAX_ERRORES_REPORTADOS = 20


def _s3():
    return boto3.client('s3')


def _ahora():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _validar_registro(registro, claves):
    if not isinstance(registro, dict):
        return 'el registro no es un objeto JSON'
    for clave in claves:
        valor = registro.get(clave)
        if not isinstance(valor, str) or not valor.strip():
            return f'falta la clave {clave} o no es texto'
    if 'tenant_id' in registro and not str(registro['tenant_id']).startswith('ten_'):
        return 'tenant_id debe empezar con ten_'
    return None


def _guardar_resultado(bucket, clave_archivo, resultado):
    nombre = clave_archivo[len(PREFIJO_ENTRADA):].rsplit('.', 1)[0]
    _s3().put_object(Bucket=bucket, Key=f'{PREFIJO_RESULTADOS}{nombre}.json',
                     Body=json.dumps(resultado, ensure_ascii=False, indent=2).encode('utf-8'),
                     ContentType='application/json')


def importar_objeto(bucket, clave_archivo, tablas):
    """Importa un objeto de S3. `tablas` = {'t_clientes': ('TABLE_CLIENTES', ('tenant_id', 'cliente_id'))}."""
    inicio = time.time()
    resultado = {'archivo': clave_archivo, 'bucket': bucket, 'fecha': _ahora(),
                 'registros_leidos': 0, 'registros_escritos': 0, 'errores': []}
    partes = clave_archivo.split('/')
    tabla = partes[1] if len(partes) == 3 else None
    if (not clave_archivo.startswith(PREFIJO_ENTRADA) or len(partes) != 3
            or not clave_archivo.endswith('.jsonl')):
        resultado.update(estado='rechazado',
                         motivo='La ruta debe ser importaciones/<tabla>/<archivo>.jsonl')
    elif tabla not in tablas:
        resultado.update(estado='rechazado', tabla=tabla,
                         motivo=f'La tabla {tabla} no pertenece a este servicio. '
                                f'Tablas permitidas: {sorted(tablas)}')
    if resultado.get('estado') == 'rechazado':
        print(json.dumps(resultado, ensure_ascii=False))
        _guardar_resultado(bucket, clave_archivo, resultado)
        return resultado

    variable, claves = tablas[tabla]
    nombre_tabla = os.environ[variable]
    resultado.update(tabla=tabla, tabla_dynamodb=nombre_tabla)
    cuerpo = _s3().get_object(Bucket=bucket, Key=clave_archivo)['Body']
    tabla_dynamo = boto3.resource('dynamodb').Table(nombre_tabla)
    errores = 0
    with tabla_dynamo.batch_writer(overwrite_by_pkeys=list(claves)) as escritor:
        for numero, linea in enumerate(cuerpo.iter_lines(), start=1):
            texto = linea.decode('utf-8').lstrip('\ufeff').strip()
            if not texto:
                continue
            resultado['registros_leidos'] += 1
            try:
                registro = json.loads(texto, parse_float=Decimal)  # DynamoDB no acepta float
            except json.JSONDecodeError as error:
                motivo = f'JSON inválido: {error.msg}'
            else:
                motivo = _validar_registro(registro, claves)
            if motivo:
                errores += 1
                if len(resultado['errores']) < MAX_ERRORES_REPORTADOS:
                    resultado['errores'].append({'linea': numero, 'motivo': motivo})
                continue
            escritor.put_item(Item=registro)
            resultado['registros_escritos'] += 1

    resultado['registros_con_error'] = errores
    resultado['estado'] = 'completado' if errores == 0 else 'con_errores'
    resultado['duracion_segundos'] = round(time.time() - inicio, 2)
    print(json.dumps(resultado, ensure_ascii=False))
    _guardar_resultado(bucket, clave_archivo, resultado)
    return resultado


def crear_handler(tablas):
    """Devuelve el lambda_handler de un servicio, limitado a sus propias tablas."""

    def lambda_handler(event, context):
        archivos = []
        for registro in event.get('Records', []):
            bucket = registro['s3']['bucket']['name']
            clave = unquote_plus(registro['s3']['object']['key'])  # S3 codifica la clave en el evento
            archivos.append(importar_objeto(bucket, clave, tablas))
        return {'archivos': archivos}

    return lambda_handler