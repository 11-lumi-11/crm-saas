"""Sube los datos generados a los buckets de importación de cada servicio y espera el resultado.

Alternativa por consola a arrastrar las carpetas en S3 (ver datos/README.md). Cada archivo subido
dispara el Lambda ImportarDatos de su servicio, que deja su reporte en resultados/.

Requisitos: pip install boto3 y credenciales de AWS Academy en %USERPROFILE%\\.aws\\credentials.

Uso:
    python datos/cargar_datos.py --stage dev                      # sube los 6 servicios y espera
    python datos/cargar_datos.py --stage dev --servicios clientes # solo uno
    python datos/cargar_datos.py --stage dev --sin-esperar        # sube y termina
"""
import argparse
import json
import sys
import time
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    sys.exit('Falta boto3. Instálelo con:  python -m pip install boto3')

RAIZ = Path(__file__).resolve().parent.parent
# carpeta del servicio -> nombre del servicio en serverless.yml
SERVICIOS = {'usuarios': 'crm-usuarios', 'clientes': 'crm-clientes', 'oportunidades': 'crm-oportunidades',
             'actividades': 'crm-actividades', 'productos_cotizaciones': 'crm-productos-cotizaciones',
             'notificaciones': 'crm-notificaciones'}


def nombre_bucket(servicio, stage, cuenta):
    # Debe coincidir con custom.bucketImportaciones de cada serverless.yml
    return f'{SERVICIOS[servicio]}-{stage}-imp-{cuenta}'


def subir(s3, bucket, carpeta):
    claves = []
    for archivo in sorted((carpeta / 'importaciones').rglob('*.jsonl')):
        clave = archivo.relative_to(carpeta).as_posix()  # importaciones/<tabla>/parte_0001.jsonl
        s3.upload_file(str(archivo), bucket, clave, ExtraArgs={'ContentType': 'application/x-ndjson'})
        claves.append(clave)
        print(f'  subido  s3://{bucket}/{clave}')
    return claves


def esperar(s3, pendientes, limite_segundos):
    """pendientes: {(bucket, clave_resultado): clave_archivo}. Devuelve los reportes obtenidos."""
    reportes, inicio = {}, time.time()
    while pendientes and time.time() - inicio < limite_segundos:
        for (bucket, clave), archivo in list(pendientes.items()):
            try:
                cuerpo = s3.get_object(Bucket=bucket, Key=clave)['Body'].read()
            except ClientError as error:
                if error.response['Error']['Code'] in ('NoSuchKey', '404'):
                    continue
                raise
            reportes[archivo] = json.loads(cuerpo)
            del pendientes[(bucket, clave)]
        if pendientes:
            print(f'  esperando {len(pendientes)} archivo(s)...')
            time.sleep(10)
    return reportes, pendientes


def main():
    parser = argparse.ArgumentParser(description='Sube los datos ficticios a S3 y espera la importación.')
    parser.add_argument('--stage', default='dev')
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('--salida', type=Path, default=RAIZ / 'datos' / 'salida')
    parser.add_argument('--servicios', nargs='+', choices=list(SERVICIOS), default=list(SERVICIOS))
    parser.add_argument('--sin-esperar', action='store_true', help='No esperar los reportes de resultados/')
    parser.add_argument('--limite', type=int, default=900, help='Segundos máximos de espera (defecto 900)')
    args = parser.parse_args()

    if not (args.salida / 'resumen.json').exists():
        sys.exit(f'No hay datos en {args.salida}. Ejecute antes: python datos/generar_datos.py')
    sesion = boto3.Session(region_name=args.region)
    try:
        cuenta = sesion.client('sts').get_caller_identity()['Account']
    except (NoCredentialsError, ClientError) as error:
        sys.exit(f'No hay credenciales válidas de AWS ({error}). Copie las de AWS Academy > AWS Details.')
    s3 = sesion.client('s3')

    pendientes = {}
    for servicio in args.servicios:
        bucket = nombre_bucket(servicio, args.stage, cuenta)
        try:
            s3.head_bucket(Bucket=bucket)
        except ClientError:
            sys.exit(f'No existe el bucket {bucket}. Despliegue antes servicios/{servicio} con --stage {args.stage}.')
        print(f'\n[{servicio}] bucket {bucket}')
        for clave in subir(s3, bucket, args.salida / servicio):
            resultado = 'resultados/' + clave[len('importaciones/'):-len('.jsonl')] + '.json'
            pendientes[(bucket, resultado)] = clave

    if args.sin_esperar:
        print('\nArchivos subidos. Revise los reportes en la carpeta resultados/ de cada bucket.')
        return 0

    print('\nEsperando que los Lambdas ImportarDatos terminen...')
    reportes, faltantes = esperar(s3, pendientes, args.limite)
    print(f'\n{"Archivo":60} {"Estado":12} {"Escritos":>9}')
    escritos = 0
    for archivo, r in sorted(reportes.items()):
        escritos += r.get('registros_escritos', 0)
        print(f'{archivo:60} {r["estado"]:12} {r.get("registros_escritos", 0):>9,}')
    malos = [a for a, r in reportes.items() if r['estado'] != 'completado']
    print(f'\nTotal escrito: {escritos:,} registros en {len(reportes)} archivos')
    if faltantes:
        print(f'Sin reporte tras {args.limite} s ({len(faltantes)}): revise CloudWatch Logs de importarDatos.')
    if malos:
        print(f'Con errores o rechazados: {malos}')
    return 1 if faltantes or malos else 0


if __name__ == '__main__':
    sys.exit(main())