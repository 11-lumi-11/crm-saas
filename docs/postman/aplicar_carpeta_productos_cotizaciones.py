"""Agrega la carpeta "5. Productos y Cotizaciones" y sus variables a la colección de Postman.
Uso (desde la raíz del repo):  python docs/postman/aplicar_carpeta_productos_cotizaciones.py
Es idempotente: si la carpeta ya existe, no hace nada. Requiere haber corrido antes la carpeta 1 (tokens)."""
import json
import pathlib

RUTA = pathlib.Path(__file__).with_name('CRM-SaaS.postman_collection.json')


def peticion(nombre, metodo, url, token=None, body=None, estado=None, codigo=None, guardar=None):
    cabeceras = [{'key': 'Content-Type', 'value': 'application/json'}] if body is not None else []
    if token:
        cabeceras.append({'key': 'Authorization', 'value': f'Bearer {{{{{token}}}}}'})
    lineas = []
    if guardar:
        campo, variable = guardar
        lineas += ['const d = pm.response.json();',
                   f"if (d.{campo}) pm.collectionVariables.set('{variable}', d.{campo});"]
    if estado:
        lineas.append(f"pm.test('Estado {estado}', () => pm.response.to.have.status({estado}));")
    if codigo:
        lineas.append(f"pm.test('codigo {codigo}', () => pm.expect(pm.response.json().codigo).to.eql('{codigo}'));")
    item = {'name': nombre, 'request': {'method': metodo, 'header': cabeceras, 'url': url}}
    if body is not None:
        item['request']['body'] = {'mode': 'raw', 'raw': json.dumps(body, indent=2, ensure_ascii=False)}
    if lineas:
        item['event'] = [{'listen': 'test', 'script': {'type': 'text/javascript', 'exec': lineas}}]
    return item


P = '{{productos_url}}'
COT = P + '/cotizaciones/{{cotizacion_id}}'
cotizacion = {'oportunidad_id': '{{oportunidad_cot_id}}', 'cliente_id': 'cli_000001',
              'items': [{'producto_id': '{{producto_id}}', 'cantidad': 10}]}

carpeta = {'name': '5. Productos y Cotizaciones', 'item': [
    peticion('Crear producto (vendedor, debe 403)', 'POST', P + '/productos', 'token_vendedor',
             {'nombre': 'Seguro vehicular básico', 'precio': 1200.5}, 403, 'prohibido'),
    peticion('Crear producto (gerente)', 'POST', P + '/productos', 'token_gerente',
             {'nombre': 'Seguro vehicular básico', 'descripcion': 'Cobertura por vehículo', 'categoria': 'vehicular',
              'precio': 1200.5, 'moneda': 'PEN'}, 201, guardar=('producto_id', 'producto_id')),
    peticion('Crear producto sin precio (debe 400)', 'POST', P + '/productos', 'token_gerente',
             {'nombre': 'Incompleto'}, 400, 'datos_incompletos'),
    peticion('Listar productos (vendedor)', 'GET', P + '/productos', 'token_vendedor', estado=200),
    peticion('Listar productos activos', 'GET', P + '/productos?estado=activo', 'token_vendedor', estado=200),
    peticion('Obtener producto', 'GET', P + '/productos/{{producto_id}}', 'token_vendedor', estado=200),
    peticion('Editar precio (gerente)', 'PUT', P + '/productos/{{producto_id}}', 'token_gerente',
             {'precio': 1250}, 200),
    peticion('Crear oportunidad para cotizar (vendedor)', 'POST', '{{oportunidades_url}}/oportunidades',
             'token_vendedor', {'cliente_id': 'cli_000001', 'titulo': 'Seguro de flota (cotización)',
                                'monto_estimado': 12500}, 201, guardar=('oportunidad_id', 'oportunidad_cot_id')),
    peticion('Crear cotización (vendedor)', 'POST', P + '/cotizaciones', 'token_vendedor', cotizacion, 201,
             guardar=('cotizacion_id', 'cotizacion_id')),
    peticion('Cotización con ítems vacíos (debe 400)', 'POST', P + '/cotizaciones', 'token_vendedor',
             {**cotizacion, 'items': []}, 400, 'datos_invalidos'),
    peticion('Obtener cotización', 'GET', COT, 'token_vendedor', estado=200),
    peticion('Aceptar un borrador (debe 409)', 'PUT', COT + '/aceptar', 'token_vendedor', estado=409,
             codigo='estado_invalido_cotizacion'),
    peticion('Enviar cotización', 'PUT', COT + '/enviar', 'token_vendedor', estado=200),
    peticion('Listar cotizaciones enviadas', 'GET', P + '/cotizaciones?estado=enviada', 'token_vendedor', estado=200),
    peticion('Aceptar cotización', 'PUT', COT + '/aceptar', 'token_vendedor', estado=200),
    peticion('Eliminar aceptada (gerente, debe 409)', 'DELETE', COT, 'token_gerente', estado=409,
             codigo='cotizacion_aceptada'),
    peticion('Ver oportunidad (ganada tras ~1 min)', 'GET', '{{oportunidades_url}}/oportunidades/{{oportunidad_cot_id}}',
             'token_vendedor', estado=200),
    peticion('Listar cotizaciones de la oportunidad', 'GET',
             P + '/cotizaciones?oportunidad_id={{oportunidad_cot_id}}', 'token_vendedor', estado=200),
    peticion('Sin token (debe 401)', 'GET', P + '/productos', None, estado=401),
]}

coleccion = json.loads(RUTA.read_text(encoding='utf-8'))
if any(i.get('name') == carpeta['name'] for i in coleccion['item']):
    print('La carpeta ya existe; no se hizo nada.')
else:
    # Se inserta antes de "6. Notificaciones" para conservar el orden numérico
    posicion = next((n for n, i in enumerate(coleccion['item']) if i.get('name', '').startswith('6.')),
                    len(coleccion['item']))
    coleccion['item'].insert(posicion, carpeta)
    claves = {v['key'] for v in coleccion.get('variable', [])}
    for clave in ('productos_url', 'producto_id', 'cotizacion_id', 'oportunidad_cot_id'):
        if clave not in claves:
            coleccion.setdefault('variable', []).append({'key': clave, 'value': ''})
    RUTA.write_text(json.dumps(coleccion, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Carpeta "5. Productos y Cotizaciones" agregada.')
