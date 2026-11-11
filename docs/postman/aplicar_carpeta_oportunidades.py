"""Agrega la carpeta "3. Oportunidades" y sus variables a la colección de Postman.
Uso (desde la raíz del repo):  python docs/postman/aplicar_carpeta_oportunidades.py
Es idempotente: si la carpeta ya existe, no hace nada. Se puede borrar después de usarlo."""
import json
import pathlib

RUTA = pathlib.Path(__file__).with_name('CRM-SaaS.postman_collection.json')


def peticion(nombre, metodo, ruta, token=None, cuerpo=None, estado=None, codigo=None, guardar_id=False):
    cabeceras = []
    if cuerpo is not None:
        cabeceras.append({'key': 'Content-Type', 'value': 'application/json'})
    if token:
        cabeceras.append({'key': 'Authorization', 'value': f'Bearer {{{{{token}}}}}'})
    elif token is None and False:
        pass
    exec_lineas = []
    if guardar_id:
        exec_lineas += ['const d = pm.response.json();',
                        "if (d.oportunidad_id) pm.collectionVariables.set('oportunidad_id', d.oportunidad_id);"]
    if estado:
        exec_lineas.append(f"pm.test('Estado {estado}', () => pm.response.to.have.status({estado}));")
    if codigo:
        exec_lineas.append(f"pm.test('codigo {codigo}', () => pm.expect(pm.response.json().codigo).to.eql('{codigo}'));")
    item = {'name': nombre, 'request': {'method': metodo, 'header': cabeceras,
                                        'url': '{{oportunidades_url}}' + ruta}}
    if cuerpo is not None:
        item['request']['body'] = {'mode': 'raw', 'raw': json.dumps(cuerpo, indent=2, ensure_ascii=False)}
    if exec_lineas:
        item['event'] = [{'listen': 'test', 'script': {'type': 'text/javascript', 'exec': exec_lineas}}]
    return item


O = '/oportunidades/{{oportunidad_id}}'
carpeta = {'name': '3. Oportunidades', 'item': [
    peticion('Crear oportunidad (vendedor)', 'POST', '/oportunidades', 'token_vendedor',
             {'cliente_id': 'cli_000001', 'cliente_nombre': 'Constructora Andes', 'titulo': 'Seguro de flota',
              'monto_estimado': 80000, 'moneda': 'PEN', 'fecha_cierre_estimada': '2026-12-15'},
             201, guardar_id=True),
    peticion('Listar oportunidades', 'GET', '/oportunidades', 'token_vendedor', estado=200),
    peticion('Listar oportunidades (etapa=nueva)', 'GET', '/oportunidades?etapa=nueva', 'token_vendedor', estado=200),
    peticion('Obtener oportunidad', 'GET', O, 'token_vendedor', estado=200),
    peticion('Editar oportunidad (vendedor)', 'PUT', O, 'token_vendedor',
             {'monto_estimado': 95000, 'probabilidad': 30}, 200),
    peticion('Vendedor reasigna responsable (debe 403)', 'PUT', O, 'token_vendedor',
             {'responsable_id': '{{usuario_gerente_id}}'}, 403, 'prohibido'),
    peticion('Cambiar etapa a calificada (200)', 'PUT', O + '/etapa', 'token_vendedor',
             {'etapa': 'calificada'}, 200),
    peticion('Ver historial', 'GET', O + '/historial', 'token_vendedor', estado=200),
    peticion('Retroceder a nueva (debe 400)', 'PUT', O + '/etapa', 'token_vendedor',
             {'etapa': 'nueva'}, 400, 'transicion_invalida'),
    peticion('Pasar a perdida sin motivo (debe 400)', 'PUT', O + '/etapa', 'token_vendedor',
             {'etapa': 'perdida'}, 400, 'motivo_requerido'),
    peticion('Pasar a ganada (gerente, 200)', 'PUT', O + '/etapa', 'token_gerente',
             {'etapa': 'ganada'}, 200),
    peticion('Editar oportunidad cerrada (debe 409)', 'PUT', O, 'token_vendedor',
             {'titulo': 'Intento de edicion'}, 409, 'oportunidad_cerrada'),
    peticion('Eliminar oportunidad (vendedor, debe 403)', 'DELETE', O, 'token_vendedor', estado=403, codigo='prohibido'),
    peticion('Eliminar oportunidad (gerente, 200)', 'DELETE', O, 'token_gerente', estado=200),
    peticion('Sin token (debe 401)', 'GET', '/oportunidades', estado=401),
    peticion('Token inválido (debe 403)', 'GET', '/oportunidades', 'token_invalido', estado=403),
]}
# El token inválido se escribe literal, no como variable
carpeta['item'][-1]['request']['header'] = [{'key': 'Authorization', 'value': 'Bearer token.falso.aqui'}]

coleccion = json.loads(RUTA.read_text(encoding='utf-8'))
if any(i.get('name') == carpeta['name'] for i in coleccion['item']):
    print('La carpeta ya existe; no se hizo nada.')
else:
    existentes = {v['key'] for v in coleccion.get('variable', [])}
    for clave in ('oportunidades_url', 'oportunidad_id'):
        if clave not in existentes:
            coleccion.setdefault('variable', []).append({'key': clave, 'value': ''})
    coleccion['item'].append(carpeta)
    coleccion['info']['name'] = 'CRM SaaS — Usuarios + Clientes + Oportunidades'
    RUTA.write_text(json.dumps(coleccion, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Carpeta "3. Oportunidades" agregada.')
