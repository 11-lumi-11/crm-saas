"""Agrega la carpeta "6. Notificaciones" y sus variables a la colección de Postman.
Uso (desde la raíz del repo):  python docs/postman/aplicar_carpeta_notificaciones.py
Es idempotente: si la carpeta ya existe, no hace nada. Se puede borrar después de usarlo."""
import json
import pathlib

RUTA = pathlib.Path(__file__).with_name('CRM-SaaS.postman_collection.json')


def peticion(nombre, metodo, ruta, token=None, estado=None, codigo=None, guardar_id=False):
    cabeceras = [{'key': 'Authorization', 'value': f'Bearer {{{{{token}}}}}'}] if token else []
    lineas = []
    if guardar_id:
        lineas += ['const d = pm.response.json();',
                   "if (d.notificaciones && d.notificaciones.length) pm.collectionVariables.set('notificacion_id', d.notificaciones[0].notificacion_id);"]
    if estado:
        lineas.append(f"pm.test('Estado {estado}', () => pm.response.to.have.status({estado}));")
    if codigo:
        lineas.append(f"pm.test('codigo {codigo}', () => pm.expect(pm.response.json().codigo).to.eql('{codigo}'));")
    item = {'name': nombre, 'request': {'method': metodo, 'header': cabeceras,
                                        'url': '{{notificaciones_url}}' + ruta}}
    if lineas:
        item['event'] = [{'listen': 'test', 'script': {'type': 'text/javascript', 'exec': lineas}}]
    return item


L = '/notificaciones/{{notificacion_id}}/leer'
carpeta = {'name': '6. Notificaciones', 'item': [
    peticion('Listar notificaciones (vendedor)', 'GET', '/notificaciones', 'token_vendedor', 200, guardar_id=True),
    peticion('Listar solo no leídas (vendedor)', 'GET', '/notificaciones?solo_no_leidas=true', 'token_vendedor', 200),
    peticion('Listar con límite 1 (paginación)', 'GET', '/notificaciones?limite=1', 'token_vendedor', 200),
    peticion('Marcar como leída (vendedor)', 'PUT', L, 'token_vendedor', 200),
    peticion('Marcar otra vez (idempotente, 200)', 'PUT', L, 'token_vendedor', 200),
    peticion('Marcar aviso ajeno (admin, debe 404)', 'PUT', L, 'token_admin', 404, 'no_encontrado'),
    peticion('Listar notificaciones (gerente)', 'GET', '/notificaciones', 'token_gerente', 200),
    peticion('Listar notificaciones (admin)', 'GET', '/notificaciones', 'token_admin', 200),
    peticion('Límite inválido (debe 400)', 'GET', '/notificaciones?limite=abc', 'token_vendedor', 400, 'datos_invalidos'),
    peticion('Sin token (debe 401)', 'GET', '/notificaciones', None, 401),
]}

coleccion = json.loads(RUTA.read_text(encoding='utf-8'))
if any(i.get('name') == carpeta['name'] for i in coleccion['item']):
    print('La carpeta ya existe; no se hizo nada.')
else:
    coleccion['item'].append(carpeta)
    claves = {v['key'] for v in coleccion.get('variable', [])}
    for clave in ('notificaciones_url', 'notificacion_id'):
        if clave not in claves:
            coleccion.setdefault('variable', []).append({'key': clave, 'value': ''})
    RUTA.write_text(json.dumps(coleccion, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Carpeta "6. Notificaciones" agregada.')
