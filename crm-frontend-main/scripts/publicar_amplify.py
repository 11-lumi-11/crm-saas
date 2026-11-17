"""Publica dist/ en una rama manual de Amplify creada por Serverless.

No muestra la URL prefirmada ni credenciales. Ejecutar después de `npm run build`
y de `serverless deploy --stage <stage>`, con boto3 y credenciales AWS disponibles.
"""
import argparse
import io
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import boto3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', default='dev')
    parser.add_argument('--region', default='us-east-1')
    args = parser.parse_args()
    carpeta = Path(__file__).resolve().parent.parent / 'dist'
    if not (carpeta / 'index.html').is_file():
        raise RuntimeError('No se encontró dist/index.html; ejecuta npm run build.')

    archivo = io.BytesIO()
    with zipfile.ZipFile(archivo, 'w', zipfile.ZIP_DEFLATED) as paquete:
        for ruta in sorted(carpeta.rglob('*')):
            if ruta.is_file():
                paquete.write(ruta, ruta.relative_to(carpeta).as_posix())
    cf = boto3.client('cloudformation', region_name=args.region)
    pila = cf.describe_stacks(StackName=f'crm-frontend-hosting-{args.stage}')['Stacks'][0]
    outputs = {item['OutputKey']: item['OutputValue'] for item in pila.get('Outputs', [])}
    app_id, dominio, rama = (outputs[k] for k in ('FrontendAppId', 'FrontendDomain', 'FrontendBranchName'))
    amplify = boto3.client('amplify', region_name=args.region)
    despliegue = amplify.create_deployment(appId=app_id, branchName=rama)
    peticion = urllib.request.Request(despliegue['zipUploadUrl'], data=archivo.getvalue(),
                                     headers={'Content-Type': 'application/zip'}, method='PUT')
    try:
        with urllib.request.urlopen(peticion, timeout=120) as respuesta:
            if not 200 <= respuesta.status < 300:
                raise RuntimeError(f'La carga del paquete falló: HTTP {respuesta.status}')
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'La carga del paquete falló: HTTP {error.code}') from None
    except urllib.error.URLError:
        raise RuntimeError('No se pudo cargar el paquete de Amplify por un error de red.') from None
    trabajo = amplify.start_deployment(appId=app_id, branchName=rama, jobId=despliegue['jobId'])
    job_id = trabajo['jobSummary']['jobId']
    print(f'Publicación iniciada: aplicación {app_id}, rama {rama}, trabajo {job_id}', flush=True)
    limite = time.monotonic() + 600
    while time.monotonic() < limite:
        resultado = amplify.get_job(appId=app_id, branchName=rama, jobId=job_id)
        estado = resultado['job']['summary']['status']
        print(f'Estado Amplify: {estado}', flush=True)
        if estado == 'SUCCEED':
            print(f'URL: https://{rama}.{dominio}', flush=True)
            return
        if estado in ('FAILED', 'CANCELLED'):
            raise RuntimeError(f'Amplify terminó la publicación con estado {estado}; revisar el trabajo {job_id}.')
        time.sleep(10)
    raise RuntimeError(f'Amplify no terminó dentro del tiempo de espera; revisar el trabajo {job_id}.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Error de publicación: {error}', file=sys.stderr)
        sys.exit(1)
