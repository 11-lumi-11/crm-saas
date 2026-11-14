"""Verifica que los datos generados por generar_datos.py sean coherentes y cumplan el enunciado.

Lee los archivos .jsonl tal como se subirán a S3 (no confía en el generador) y comprueba:
conteos mínimos, claves únicas, referencias entre servicios dentro del mismo tenant, reglas
de negocio de cada servicio y formatos (prefijos, fechas ISO 8601 UTC, montos).

Uso:
    python datos/verificar_datos.py                 # verifica datos/salida
    python datos/verificar_datos.py --salida otra/carpeta

Termina con código 0 si todo está bien y 1 si encuentra algún error.
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'compartido' / 'capa_comun' / 'python'))
from crm_comun.contrasenas import verificar  # noqa: E402

MINIMO_POR_TENANT = 10_000
AHORA = '2026-11-14T12:00:00Z'
FECHA = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
ETAPAS = ['nueva', 'calificada', 'propuesta', 'en_negociacion', 'ganada', 'perdida']
PROBABILIDAD = {'nueva': 10, 'calificada': 25, 'propuesta': 50, 'en_negociacion': 75,
                'ganada': 100, 'perdida': 0}
PRINCIPALES = ['t_usuarios', 't_clientes', 't_oportunidades', 't_actividades',
               't_cotizaciones', 't_notificaciones']
CLAVES = {
    't_tenants': ('tenant_id',), 't_tenants_locks': ('nombre_normalizado',),
    't_usuarios': ('tenant_id', 'usuario_id'), 't_correos_locks': ('correo',),
    't_clientes': ('tenant_id', 'cliente_id'), 't_contactos': ('tenant_id', 'contacto_id'),
    't_oportunidades': ('tenant_id', 'oportunidad_id'),
    't_historial_etapas': ('tenant_id', 'historial_id'),
    't_actividades': ('tenant_id', 'actividad_id'),
    't_oportunidades_control_actividades': ('tenant_id', 'oportunidad_id'),
    't_productos': ('tenant_id', 'producto_id'), 't_cotizaciones': ('tenant_id', 'cotizacion_id'),
    't_notificaciones': ('tenant_id', 'notificacion_id'),
    't_lecturas_notificaciones': ('tenant_id', 'lectura_id'),
}
PREFIJOS = {'usuario_id': 'usr', 'cliente_id': 'cli', 'contacto_id': 'con', 'oportunidad_id': 'opo',
            'historial_id': 'his', 'actividad_id': 'act', 'producto_id': 'pro',
            'cotizacion_id': 'cot', 'notificacion_id': 'not', 'evento_id': 'evt',
            'responsable_id': 'usr', 'creada_por': 'usr', 'respondida_por': 'usr',
            'usuario_destino_id': 'usr', 'contacto_principal_id': 'con'}


class Informe:
    def __init__(self):
        self.errores = Counter()
        self.ejemplos = {}
        self.chequeos = 0

    def exigir(self, condicion, regla, ejemplo=''):
        self.chequeos += 1
        if not condicion:
            self.errores[regla] += 1
            self.ejemplos.setdefault(regla, ejemplo)


def cargar(salida):
    tablas = {}
    for archivo in sorted(salida.glob('*/importaciones/*/parte_*.jsonl')):
        tabla = archivo.parent.name
        with open(archivo, encoding='utf-8') as f:
            tablas.setdefault(tabla, []).extend(json.loads(linea) for linea in f if linea.strip())
    return tablas


def verificar_formatos(tablas, inf):
    for tabla, registros in tablas.items():
        claves = Counter(tuple(r[c] for c in CLAVES[tabla]) for r in registros)
        repetidas = [k for k, n in claves.items() if n > 1]
        inf.exigir(not repetidas, f'{tabla}: clave primaria repetida', repetidas[:1])
        for r in registros:
            for campo, valor in r.items():
                if campo.startswith('fecha_'):
                    inf.exigir(isinstance(valor, str) and FECHA.match(valor),
                               f'{tabla}.{campo}: fecha no es ISO 8601 UTC', valor)
                    if campo not in ('fecha_vencimiento', 'fecha_cierre_estimada', 'fecha_programada'):
                        inf.exigir(valor <= AHORA, f'{tabla}.{campo}: fecha en el futuro', valor)
                prefijo = PREFIJOS.get(campo)
                if prefijo and not (campo == 'usuario_id' and valor == 'sistema'):
                    inf.exigir(isinstance(valor, str) and re.fullmatch(prefijo + r'_[A-Za-z0-9]+', valor),
                               f'{tabla}.{campo}: identificador sin prefijo {prefijo}_', valor)
            if 'fecha_creacion' in r and 'fecha_actualizacion' in r:
                inf.exigir(r['fecha_actualizacion'] >= r['fecha_creacion'],
                           f'{tabla}: actualización anterior a la creación', r)


def verificar_conteos(tablas, inf):
    tenants = {t['tenant_id'] for t in tablas['t_tenants']}
    inf.exigir(len(tenants) == 3, 'Debe haber exactamente 3 tenants', tenants)
    for tabla in PRINCIPALES:
        por_tenant = Counter(r['tenant_id'] for r in tablas[tabla])
        inf.exigir(sum(por_tenant.values()) >= 3 * MINIMO_POR_TENANT,
                   f'{tabla}: menos de 30,000 registros', sum(por_tenant.values()))
        for t in tenants:
            inf.exigir(por_tenant[t] >= MINIMO_POR_TENANT, f'{tabla}: menos de 10,000 en un tenant',
                       (t, por_tenant[t]))


def verificar_usuarios(tablas, inf, idx):
    correos = Counter(u['correo'] for u in tablas['t_usuarios'])
    inf.exigir(max(correos.values()) == 1, 't_usuarios: correo repetido (debe ser único global)')
    candados = {c['correo']: c for c in tablas['t_correos_locks']}
    hashes = set()
    for u in tablas['t_usuarios']:
        inf.exigir(u['tenant_id'] in idx['tenants'], 't_usuarios: tenant inexistente', u['tenant_id'])
        inf.exigir(u['rol'] in ('admin', 'gerente', 'vendedor'), 't_usuarios: rol inválido', u['rol'])
        inf.exigir(u['estado'] in ('activo', 'inactivo'), 't_usuarios: estado inválido', u['estado'])
        inf.exigir(u['correo'] == u['correo'].strip().lower(), 't_usuarios: correo no normalizado', u['correo'])
        c = candados.get(u['correo'])
        inf.exigir(c and c['tenant_id'] == u['tenant_id'] and c['usuario_id'] == u['usuario_id'],
                   't_correos_locks: candado ausente o de otro usuario', u['correo'])
        hashes.add(u['contrasena_hash'])
    inf.exigir(len(candados) == len(tablas['t_usuarios']), 't_correos_locks: candados sobrantes')
    for h in hashes:  # todos comparten uno: se verifica que la contraseña demo funcione
        inf.exigir(verificar('Demo2026!', h), 't_usuarios: el hash no corresponde a Demo2026!', h[:30])
    for t in idx['tenants']:
        roles = Counter(u['rol'] for u in tablas['t_usuarios'] if u['tenant_id'] == t and u['estado'] == 'activo')
        inf.exigir(roles['admin'] >= 1 and roles['gerente'] >= 1, 'Cada tenant necesita admin y gerente activos', t)
    for lock in tablas['t_tenants_locks']:
        inf.exigir(lock['nombre_normalizado'] in {t['nombre_normalizado'] for t in tablas['t_tenants']},
                   't_tenants_locks: candado sin tenant')


def verificar_clientes(tablas, inf, idx):
    principales = Counter()
    for k in tablas['t_contactos']:
        cliente = idx['clientes'].get((k['tenant_id'], k['cliente_id']))
        inf.exigir(cliente, 't_contactos: cliente inexistente en su tenant', k['contacto_id'])
        inf.exigir(isinstance(k['es_principal'], bool), 't_contactos: es_principal no es booleano')
        if k['es_principal']:
            principales[(k['tenant_id'], k['cliente_id'])] += 1
            inf.exigir(cliente and cliente.get('contacto_principal_id') == k['contacto_id'],
                       't_clientes: contacto_principal_id no coincide con el contacto principal', k['contacto_id'])
    inf.exigir(not principales or max(principales.values()) == 1, 't_contactos: más de un principal por cliente')
    for c in tablas['t_clientes']:
        u = idx['usuarios'].get((c['tenant_id'], c['responsable_id']))
        inf.exigir(u, 't_clientes: responsable no existe en el tenant', c['cliente_id'])
        inf.exigir(u and u['estado'] == 'activo', 't_clientes: responsable inactivo', c['cliente_id'])
        inf.exigir(u and u['fecha_creacion'] <= c['fecha_creacion'],
                   't_clientes: el responsable se creó después que el cliente', c['cliente_id'])
        inf.exigir(c['tipo'] in ('empresa', 'persona'), 't_clientes: tipo inválido')
        inf.exigir(c['estado'] in ('prospecto', 'activo', 'inactivo'), 't_clientes: estado inválido')
        largo = 11 if c['tipo'] == 'empresa' else 8
        inf.exigir(len(c['documento']) == largo and c['documento'].isdigit(),
                   't_clientes: RUC/DNI con longitud incorrecta', c['documento'])
        if 'contacto_principal_id' in c:
            inf.exigir((c['tenant_id'], c['cliente_id']) in principales,
                       't_clientes: contacto_principal_id apunta a un contacto no principal')


def verificar_oportunidades(tablas, inf, idx):
    historial = defaultdict(list)
    for h in tablas['t_historial_etapas']:
        historial[(h['tenant_id'], h['oportunidad_id'])].append(h)
    aceptadas = Counter((c['tenant_id'], c['oportunidad_id']) for c in tablas['t_cotizaciones']
                        if c['estado'] == 'aceptada')
    for o in tablas['t_oportunidades']:
        clave = (o['tenant_id'], o['oportunidad_id'])
        cliente = idx['clientes'].get((o['tenant_id'], o['cliente_id']))
        inf.exigir(cliente, 't_oportunidades: cliente inexistente en su tenant', o['oportunidad_id'])
        inf.exigir(cliente and cliente['nombre'] == o.get('cliente_nombre'),
                   't_oportunidades: cliente_nombre no coincide', o['oportunidad_id'])
        inf.exigir(cliente and cliente['fecha_creacion'] <= o['fecha_creacion'],
                   't_oportunidades: creada antes que su cliente', o['oportunidad_id'])
        if o['etapa'] not in ('ganada', 'perdida'):
            inf.exigir(cliente and cliente['estado'] != 'inactivo',
                       't_oportunidades: oportunidad abierta de cliente inactivo', o['oportunidad_id'])
        inf.exigir((o['tenant_id'], o['responsable_id']) in idx['usuarios'],
                   't_oportunidades: responsable no existe en el tenant', o['oportunidad_id'])
        inf.exigir(o['etapa'] in ETAPAS, 't_oportunidades: etapa inválida', o['etapa'])
        inf.exigir(o['probabilidad'] == PROBABILIDAD[o['etapa']],
                   't_oportunidades: probabilidad no corresponde a la etapa', o['oportunidad_id'])
        inf.exigir(o['moneda'] in ('PEN', 'USD'), 't_oportunidades: moneda inválida')
        inf.exigir(isinstance(o['monto_estimado'], (int, float)) and 0 <= o['monto_estimado'] <= 10**12,
                   't_oportunidades: monto fuera de rango')
        inf.exigir(('motivo_perdida' in o) == (o['etapa'] == 'perdida'),
                   't_oportunidades: motivo_perdida solo en perdidas', o['oportunidad_id'])
        cambios = sorted(historial.get(clave, []), key=lambda h: (h['fecha_cambio'], ETAPAS.index(h['etapa_nueva'])))
        actual = 'nueva'
        for h in cambios:
            inf.exigir(h['etapa_anterior'] == actual, 'Historial: cadena de etapas rota', o['oportunidad_id'])
            avanza = (ETAPAS.index(h['etapa_nueva']) > ETAPAS.index(h['etapa_anterior'])
                      and h['etapa_anterior'] not in ('ganada', 'perdida'))
            inf.exigir(avanza, 'Historial: retrocede o reabre una etapa', o['oportunidad_id'])
            inf.exigir(h['fecha_cambio'] >= o['fecha_creacion'], 'Historial: cambio antes de crearse')
            if h['usuario_id'] == 'sistema':
                inf.exigir(h['etapa_nueva'] == 'ganada' and aceptadas[clave] == 1,
                           "Historial: 'sistema' sin cotización aceptada", o['oportunidad_id'])
            else:
                inf.exigir((o['tenant_id'], h['usuario_id']) in idx['usuarios'],
                           'Historial: usuario inexistente', h['usuario_id'])
            actual = h['etapa_nueva']
        inf.exigir(actual == o['etapa'], 'Historial: no termina en la etapa actual', o['oportunidad_id'])
        if aceptadas[clave]:
            inf.exigir(cambios and cambios[-1]['usuario_id'] == 'sistema',
                       "Oportunidad ganada por cotización sin cambio de 'sistema'", o['oportunidad_id'])


def verificar_cotizaciones(tablas, inf, idx):
    productos = {(p['tenant_id'], p['producto_id']): p for p in tablas['t_productos']}
    aceptadas = Counter()
    for c in tablas['t_cotizaciones']:
        o = idx['oportunidades'].get((c['tenant_id'], c['oportunidad_id']))
        inf.exigir(o, 't_cotizaciones: oportunidad inexistente en su tenant', c['cotizacion_id'])
        if not o:
            continue
        inf.exigir(c['cliente_id'] == o['cliente_id'], 't_cotizaciones: cliente distinto al de la oportunidad')
        inf.exigir(c['moneda'] == o['moneda'], 't_cotizaciones: moneda distinta a la oportunidad')
        inf.exigir(c['creada_por'] == o['responsable_id'], 't_cotizaciones: creada_por no es el responsable')
        inf.exigir(c['fecha_creacion'] >= o['fecha_creacion'], 't_cotizaciones: anterior a su oportunidad')
        inf.exigir(1 <= len(c['items']) <= 50, 't_cotizaciones: debe tener de 1 a 50 ítems')
        vistos, suma = set(), 0
        for i in c['items']:
            p = productos.get((c['tenant_id'], i['producto_id']))
            inf.exigir(p, 't_cotizaciones: producto inexistente en su tenant', i['producto_id'])
            inf.exigir(i['producto_id'] not in vistos, 't_cotizaciones: producto repetido')
            vistos.add(i['producto_id'])
            if p:
                inf.exigir(p['estado'] == 'activo', 't_cotizaciones: producto inactivo cotizado', i['producto_id'])
                inf.exigir(p['moneda'] == c['moneda'], 't_cotizaciones: producto de otra moneda')
                inf.exigir(p['precio'] == i['precio_unitario'] and p['nombre'] == i['nombre_producto'],
                           't_cotizaciones: copia de nombre/precio no coincide con el catálogo')
            inf.exigir(isinstance(i['cantidad'], int) and 1 <= i['cantidad'] <= 100_000,
                       't_cotizaciones: cantidad fuera de rango')
            inf.exigir(abs(i['subtotal'] - i['cantidad'] * i['precio_unitario']) < 0.006,
                       't_cotizaciones: subtotal mal calculado', i)
            suma += i['subtotal']
        inf.exigir(abs(c['total'] - suma) < 0.006, 't_cotizaciones: total mal calculado', c['cotizacion_id'])
        estado = c['estado']
        inf.exigir(estado in ('borrador', 'enviada', 'aceptacion_pendiente', 'aceptada', 'rechazada'),
                   't_cotizaciones: estado inválido', estado)
        inf.exigir(('fecha_envio' in c) == (estado != 'borrador'), 't_cotizaciones: fecha_envio incoherente con estado')
        if 'fecha_envio' in c:
            inf.exigir(c['fecha_creacion'] <= c['fecha_envio'], 't_cotizaciones: enviada antes de crearse')
        if estado in ('aceptada', 'rechazada'):
            inf.exigir(c.get('fecha_respuesta', '') >= c['fecha_envio'] and 'respondida_por' in c,
                       't_cotizaciones: respuesta sin fecha/usuario o antes del envío', c['cotizacion_id'])
        if estado == 'aceptada':
            aceptadas[(c['tenant_id'], c['oportunidad_id'])] += 1
            inf.exigir(o['etapa'] == 'ganada', 't_cotizaciones: aceptada en oportunidad no ganada', c['cotizacion_id'])
            inf.exigir(c.get('solicitud_aceptacion_id') == c.get('resultado_solicitud_id'),
                       't_cotizaciones: solicitud y resultado de aceptación no coinciden')
        if estado in ('borrador', 'enviada'):
            inf.exigir(o['etapa'] in ('propuesta', 'en_negociacion'),
                       't_cotizaciones: cotización vigente en oportunidad cerrada', c['cotizacion_id'])
            inf.exigir(c['fecha_vencimiento'] > AHORA, 't_cotizaciones: vigente pero vencida (no sirve en la demo)')
    inf.exigir(not aceptadas or max(aceptadas.values()) == 1, 't_cotizaciones: más de una aceptada por oportunidad')
    for p in tablas['t_productos']:
        inf.exigir(0 <= p['precio'] <= 10**12 and p['moneda'] in ('PEN', 'USD'), 't_productos: precio o moneda inválidos')


def verificar_actividades(tablas, inf, idx):
    perdidas = {(o['tenant_id'], o['oportunidad_id']) for o in tablas['t_oportunidades'] if o['etapa'] == 'perdida'}
    control = {(r['tenant_id'], r['oportunidad_id']) for r in tablas['t_oportunidades_control_actividades']
               if r.get('perdida') is True}
    inf.exigir(control == perdidas, 'Barrera de Actividades: no coincide con las oportunidades perdidas',
               (len(control), len(perdidas)))
    for a in tablas['t_actividades']:
        inf.exigir((a['tenant_id'], a['cliente_id']) in idx['clientes'], 't_actividades: cliente inexistente')
        inf.exigir((a['tenant_id'], a['responsable_id']) in idx['usuarios'], 't_actividades: responsable inexistente')
        inf.exigir(a['tipo'] in ('llamada', 'reunion', 'correo', 'tarea'), 't_actividades: tipo inválido')
        inf.exigir(a['estado'] in ('pendiente', 'completada', 'cancelada'), 't_actividades: estado inválido')
        inf.exigir(a['origen'] in ('manual', 'automatica'), 't_actividades: origen inválido')
        inf.exigir(a['version'] == (1 if a['estado'] == 'pendiente' else 2), 't_actividades: versión incoherente')
        if 'oportunidad_id' in a:
            o = idx['oportunidades'].get((a['tenant_id'], a['oportunidad_id']))
            inf.exigir(o, 't_actividades: oportunidad inexistente', a['actividad_id'])
            if o:
                inf.exigir(o['cliente_id'] == a['cliente_id'], 't_actividades: cliente distinto al de su oportunidad')
                if o['etapa'] == 'perdida':
                    inf.exigir(a['estado'] != 'pendiente', 't_actividades: pendiente en oportunidad perdida',
                               a['actividad_id'])
        else:
            inf.exigir(a['origen'] == 'manual', 't_actividades: automática sin oportunidad')


def verificar_notificaciones(tablas, inf, idx):
    roles = defaultdict(set)
    for (t, _), u in idx['usuarios'].items():
        roles[t].add(u['rol'])
    avisos = {}
    for n in tablas['t_notificaciones']:
        avisos[(n['tenant_id'], n['notificacion_id'])] = n
        if 'usuario_destino_id' in n:
            inf.exigir((n['tenant_id'], n['usuario_destino_id']) in idx['usuarios'],
                       't_notificaciones: destinatario inexistente', n['notificacion_id'])
            esperado = f"{n['tenant_id']}#usr#{n['usuario_destino_id']}"
        else:
            inf.exigir(n.get('rol_destino') in roles[n['tenant_id']], 't_notificaciones: rol destino inválido')
            esperado = f"{n['tenant_id']}#rol#{n.get('rol_destino')}"
        inf.exigir(n['destino'] == esperado, 't_notificaciones: destino con formato incorrecto', n['destino'])
        huella = hashlib.sha256(f"{n['tenant_id']}|{n['evento_id']}|{n['destino']}".encode()).hexdigest()[:32]
        inf.exigir(n['notificacion_id'] == f'not_{huella}', 't_notificaciones: id no determinista', n['notificacion_id'])
        inf.exigir(n['orden'] == f"{n['fecha_creacion']}#{n['notificacion_id']}", 't_notificaciones: orden incorrecto')
        inf.exigir('{' not in n['mensaje'] and n['titulo'], 't_notificaciones: plantilla sin completar', n['mensaje'])
    for lectura in tablas['t_lecturas_notificaciones']:
        n = avisos.get((lectura['tenant_id'], lectura['notificacion_id']))
        inf.exigir(n, 't_lecturas: aviso inexistente')
        inf.exigir(lectura['lectura_id'] == f"{lectura['notificacion_id']}#{lectura['usuario_id']}",
                   't_lecturas: lectura_id con formato incorrecto')
        u = idx['usuarios'].get((lectura['tenant_id'], lectura['usuario_id']))
        inf.exigir(u, 't_lecturas: usuario inexistente')
        if n and u:
            visible = n.get('usuario_destino_id') == u['usuario_id'] or n.get('rol_destino') == u['rol']
            inf.exigir(visible, 't_lecturas: el usuario no podía ver ese aviso')
            inf.exigir(lectura['fecha_lectura'] >= n['fecha_creacion'], 't_lecturas: leído antes de existir')


def main():
    parser = argparse.ArgumentParser(description='Verifica los datos ficticios generados.')
    parser.add_argument('--salida', type=Path, default=RAIZ / 'datos' / 'salida')
    args = parser.parse_args()
    tablas = cargar(args.salida)
    faltantes = set(CLAVES) - set(tablas)
    if faltantes:
        sys.exit(f'Faltan tablas en {args.salida}: {sorted(faltantes)}. Ejecute primero generar_datos.py')

    idx = {'tenants': {t['tenant_id'] for t in tablas['t_tenants']},
           'usuarios': {(u['tenant_id'], u['usuario_id']): u for u in tablas['t_usuarios']},
           'clientes': {(c['tenant_id'], c['cliente_id']): c for c in tablas['t_clientes']},
           'oportunidades': {(o['tenant_id'], o['oportunidad_id']): o for o in tablas['t_oportunidades']}}
    inf = Informe()
    for paso in (verificar_formatos, verificar_conteos):
        paso(tablas, inf)
    for paso in (verificar_usuarios, verificar_clientes, verificar_oportunidades,
                 verificar_cotizaciones, verificar_actividades, verificar_notificaciones):
        paso(tablas, inf, idx)

    print(f'Registros leídos: {sum(len(r) for r in tablas.values()):,} en {len(tablas)} tablas')
    print(f'Comprobaciones realizadas: {inf.chequeos:,}')
    if not inf.errores:
        print('RESULTADO: OK, los datos son coherentes y cumplen el mínimo de 30,000 por microservicio.')
        return 0
    print(f'RESULTADO: {sum(inf.errores.values()):,} errores en {len(inf.errores)} reglas\n')
    for regla, cantidad in inf.errores.most_common():
        print(f'  [{cantidad:>6,}] {regla}')
        print(f'           ejemplo: {str(inf.ejemplos[regla])[:150]}')
    return 1


if __name__ == '__main__':
    sys.exit(main())