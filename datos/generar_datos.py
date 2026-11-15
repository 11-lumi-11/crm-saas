"""Generador de datos ficticios coherentes para el CRM SaaS (CS2032 · Proyecto Final).

Genera 10,000 registros por tenant (30,000 en total) en la tabla principal de cada
microservicio, más sus tablas acompañantes, respetando las reglas de negocio de cada
servicio (ver docs/documento_base.md, secciones 7 y 10).

Salida: un archivo JSON Lines (.jsonl) por cada 5,000 registros, organizado así:

    datos/salida/<servicio>/importaciones/<tabla>/parte_0001.jsonl

Para cargar, se sube la carpeta `importaciones` de cada servicio a la raíz del bucket
de importación de ese servicio; el evento de S3 dispara su Lambda `ImportarDatos`.

Uso (solo necesita Python 3.10 o superior, sin librerías externas):

    python datos/generar_datos.py
    python datos/generar_datos.py --por-tenant 100     # prueba rápida

La generación es determinista: con la misma semilla produce exactamente los mismos datos.
"""
import argparse
import hashlib
import json
import random
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'compartido' / 'capa_comun' / 'python'))
from crm_comun.contrasenas import crear_hash  # noqa: E402  (mismo hash que usa el servicio Usuarios)

# --------------------------------------------------------------------------------------
# Parámetros generales
# --------------------------------------------------------------------------------------

AHORA = datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc)
INICIO = datetime(2026, 1, 5, 9, 0, 0, tzinfo=timezone.utc)
CONTRASENA_DEMO = 'Demo2026!'

ETAPAS = ['nueva', 'calificada', 'propuesta', 'en_negociacion', 'ganada', 'perdida']
ABIERTAS = ['nueva', 'calificada', 'propuesta', 'en_negociacion']
PROBABILIDAD = {'nueva': 10, 'calificada': 25, 'propuesta': 50, 'en_negociacion': 75,
                'ganada': 100, 'perdida': 0}
PESO_ETAPA = {'nueva': 14, 'calificada': 14, 'propuesta': 16, 'en_negociacion': 16,
              'ganada': 20, 'perdida': 20}

GERENTES_POR_TENANT = 50
VENDEDORES_CON_CARTERA = 80    # vendedores que concentran la cartera comercial del tenant

# Qué tabla pertenece a qué servicio (cada servicio solo importa sus propias tablas)
SERVICIO_DE_TABLA = {
    't_tenants': 'usuarios', 't_tenants_locks': 'usuarios', 't_usuarios': 'usuarios',
    't_correos_locks': 'usuarios',
    't_clientes': 'clientes', 't_contactos': 'clientes',
    't_oportunidades': 'oportunidades', 't_historial_etapas': 'oportunidades',
    't_actividades': 'actividades', 't_oportunidades_control_actividades': 'actividades',
    't_productos': 'productos_cotizaciones', 't_cotizaciones': 'productos_cotizaciones',
    't_notificaciones': 'notificaciones', 't_lecturas_notificaciones': 'notificaciones',
}

# --------------------------------------------------------------------------------------
# Catálogos de texto
# --------------------------------------------------------------------------------------

NOMBRES = ['Lucía', 'Marta', 'Rodrigo', 'Camila', 'Diego', 'Valeria', 'José', 'Andrea', 'Luis',
           'Daniela', 'Carlos', 'Fernanda', 'Jorge', 'Gabriela', 'Miguel', 'Sofía', 'Renzo',
           'Alejandra', 'Kevin', 'Milagros', 'Jesús', 'Rosa', 'Piero', 'Carmen', 'Bruno',
           'Patricia', 'Sebastián', 'Claudia', 'Gonzalo', 'Mariana', 'Álvaro', 'Ximena',
           'Manuel', 'Katherine', 'Ricardo', 'Lorena', 'César', 'Pamela', 'Raúl', 'Jimena',
           'Óscar', 'Diana', 'Martín', 'Paola', 'Héctor', 'Silvia', 'Iván', 'Natalia',
           'Joaquín', 'Brenda', 'Fabián', 'Yesenia', 'Eduardo', 'Maribel', 'Hugo', 'Tatiana',
           'Gustavo', 'Liliana', 'Walter', 'Noemí']
APELLIDOS = ['Quispe', 'Flores', 'Sánchez', 'Rodríguez', 'García', 'Rojas', 'Huamán', 'Mamani',
             'Torres', 'Chávez', 'Díaz', 'Ramírez', 'Mendoza', 'Vásquez', 'Castillo', 'Paredes',
             'Salas', 'Ccori', 'Gutiérrez', 'Espinoza', 'Cruz', 'Ríos', 'Vargas', 'Ramos',
             'Castro', 'Palomino', 'Huanca', 'Condori', 'Aguilar', 'Medina', 'Romero', 'Silva',
             'Herrera', 'Morales', 'Cárdenas', 'Valdivia', 'Zevallos', 'Benites', 'Arias',
             'Delgado', 'Ponce', 'Tello', 'Villanueva', 'Cabrera', 'Lozano', 'Alvarado',
             'Bustamante', 'Carbajal', 'Miranda', 'Soto', 'Peña', 'Chumpitaz', 'Inga', 'Apaza',
             'Ticona', 'Saavedra', 'Lazo', 'Olivares', 'Reátegui', 'Panduro']
CIUDADES = (['Lima'] * 12 + ['Arequipa'] * 3 + ['Trujillo'] * 3 + ['Chiclayo'] * 2 +
            ['Piura'] * 2 + ['Cusco'] * 2 + ['Huancayo'] * 2 + ['Iquitos', 'Tacna', 'Ica',
             'Puno', 'Cajamarca', 'Chimbote', 'Ayacucho', 'Pucallpa', 'Huánuco'])
INDUSTRIAS = ['Construcción', 'Transporte', 'Minería', 'Agroindustria', 'Retail', 'Educación',
              'Salud', 'Hotelería', 'Restaurantes', 'Manufactura', 'Logística', 'Banca',
              'Telecomunicaciones', 'Inmobiliaria', 'Textil', 'Pesca', 'Energía', 'Servicios']
NUCLEOS_EMPRESA = ['Andes', 'Pacífico', 'Inca', 'Sol', 'Cóndor', 'Amazonía', 'Titicaca',
                   'Rímac', 'Misti', 'Huascarán', 'Paracas', 'Nazca', 'Chavín', 'Moche',
                   'Wari', 'Tumbes', 'Pachacámac', 'Mantaro', 'Colca', 'Marañón', 'Vilcanota',
                   'Lurín', 'Chillón', 'Sechura', 'Callao', 'Machu', 'Kuélap', 'Sipán']
TIPOS_EMPRESA = {'Construcción': 'Constructora', 'Transporte': 'Transportes',
                 'Minería': 'Minera', 'Agroindustria': 'Agrícola', 'Retail': 'Comercial',
                 'Educación': 'Colegio', 'Salud': 'Clínica', 'Hotelería': 'Hotel',
                 'Restaurantes': 'Restaurante', 'Manufactura': 'Industrias',
                 'Logística': 'Logística', 'Banca': 'Financiera', 'Telecomunicaciones': 'Telecom',
                 'Inmobiliaria': 'Inmobiliaria', 'Textil': 'Textil', 'Pesca': 'Pesquera',
                 'Energía': 'Energía', 'Servicios': 'Servicios Generales'}
SUFIJOS_EMPRESA = ['S.A.C.', 'S.A.', 'E.I.R.L.', 'S.R.L.', 'S.A.A.']
CARGOS = ['Gerente general', 'Gerente de compras', 'Jefe de logística', 'Jefe de operaciones',
          'Analista de compras', 'Gerente de administración', 'Jefe de sistemas',
          'Coordinador de proyectos', 'Asistente de gerencia', 'Gerente financiero']
MOTIVOS_PERDIDA = ['Eligió a la competencia', 'Precio fuera de presupuesto',
                   'El cliente postergó la compra', 'No hubo respuesta del cliente',
                   'Requisitos técnicos no cubiertos', 'Cambio de prioridades del cliente',
                   'Condiciones de pago no aceptadas']
MOTIVOS_RECHAZO = ['El precio supera el presupuesto aprobado', 'Solicitan más descuento',
                   'Prefieren otra propuesta', 'Cambiaron las cantidades requeridas',
                   'Plazo de entrega muy largo']

TENANTS = [
    {
        'tenant_id': 'ten_seguros', 'nombre': 'Seguros Andinos', 'rubro': 'Seguros',
        'dominio': 'seguros.pe',
        'demo': [('Lucía', 'Paredes', 'admin@seguros.pe', 'admin'),
                 ('Rodrigo', 'Salas', 'gerente@seguros.pe', 'gerente'),
                 ('Marta', 'Quispe', 'marta@seguros.pe', 'vendedor')],
        'productos': [  # (nombre, categoría, precio mínimo, precio máximo, moneda)
            ('Seguro vehicular básico', 'Vehicular', 1200, 2600, 'PEN'),
            ('Seguro vehicular todo riesgo', 'Vehicular', 2800, 6500, 'PEN'),
            ('Seguro de flota empresarial', 'Vehicular', 15000, 60000, 'PEN'),
            ('SOAT corporativo', 'Vehicular', 90, 250, 'PEN'),
            ('Seguro de salud individual', 'Salud', 1800, 4800, 'PEN'),
            ('Seguro de salud familiar', 'Salud', 4500, 12000, 'PEN'),
            ('EPS corporativa', 'Salud', 20000, 90000, 'PEN'),
            ('Seguro oncológico', 'Salud', 900, 2500, 'PEN'),
            ('Seguro de vida ley', 'Vida', 300, 1200, 'PEN'),
            ('Seguro de vida con ahorro', 'Vida', 2400, 9000, 'PEN'),
            ('Seguro de desgravamen', 'Vida', 400, 1500, 'PEN'),
            ('Seguro multirriesgo empresarial', 'Patrimonial', 8000, 45000, 'PEN'),
            ('Seguro contra incendio', 'Patrimonial', 3000, 20000, 'PEN'),
            ('Seguro de hogar', 'Patrimonial', 600, 2200, 'PEN'),
            ('Seguro de responsabilidad civil', 'Patrimonial', 5000, 30000, 'PEN'),
            ('SCTR salud y pensión', 'Laboral', 2500, 18000, 'PEN'),
            ('Seguro de transporte de carga', 'Transporte', 4000, 25000, 'PEN'),
            ('Seguro de equipo electrónico', 'Patrimonial', 1500, 8000, 'PEN'),
            ('Seguro agrícola', 'Agro', 6000, 35000, 'PEN'),
            ('Seguro de viaje corporativo', 'Viajes', 350, 1800, 'PEN'),
        ],
        'variantes': ['Plan Esencial', 'Plan Plus', 'Plan Premium'],
        'titulos': ['Seguro de flota para {c}', 'Renovación de póliza vehicular - {c}',
                    'EPS corporativa para {c}', 'SCTR anual - {c}', 'Multirriesgo para {c}',
                    'Seguro de vida ley - {c}', 'Programa de salud para colaboradores de {c}',
                    'Cobertura de carga para {c}', 'Responsabilidad civil - {c}'],
        'monto': (5000, 250000), 'usd': 0.0, 'cantidad': (1, 40),
    },
    {
        'tenant_id': 'ten_electro', 'nombre': 'ElectroHogar', 'rubro': 'Venta de electrodomésticos',
        'dominio': 'electro.pe',
        'demo': [('Camila', 'Rojas', 'admin@electro.pe', 'admin'),
                 ('Jorge', 'Huamán', 'gerente@electro.pe', 'gerente'),
                 ('Diego', 'Flores', 'vendedor@electro.pe', 'vendedor')],
        'productos': [
            ('Refrigeradora No Frost 400 L', 'Refrigeración', 1800, 3200, 'PEN'),
            ('Refrigeradora side by side', 'Refrigeración', 3800, 7500, 'PEN'),
            ('Congeladora horizontal 300 L', 'Refrigeración', 1300, 2400, 'PEN'),
            ('Lavadora 18 kg', 'Lavado', 1400, 2600, 'PEN'),
            ('Lavaseca 12 kg', 'Lavado', 2200, 3900, 'PEN'),
            ('Secadora a gas', 'Lavado', 1900, 3500, 'PEN'),
            ('Televisor LED 55"', 'Televisores', 1600, 2900, 'PEN'),
            ('Televisor QLED 65"', 'Televisores', 2900, 5800, 'PEN'),
            ('Televisor 85" para salas', 'Televisores', 6500, 12000, 'PEN'),
            ('Cocina a gas 5 hornillas', 'Cocina', 900, 2100, 'PEN'),
            ('Horno microondas 30 L', 'Cocina', 280, 650, 'PEN'),
            ('Campana extractora', 'Cocina', 450, 1400, 'PEN'),
            ('Aire acondicionado split 12000 BTU', 'Climatización', 1500, 2800, 'PEN'),
            ('Aire acondicionado split 24000 BTU', 'Climatización', 2700, 4600, 'PEN'),
            ('Terma eléctrica 80 L', 'Climatización', 650, 1300, 'PEN'),
            ('Laptop corporativa 14"', 'Cómputo', 2300, 4800, 'PEN'),
            ('Monitor 27"', 'Cómputo', 650, 1500, 'PEN'),
            ('Licuadora industrial', 'Pequeños electrodomésticos', 350, 1200, 'PEN'),
            ('Cafetera espresso', 'Pequeños electrodomésticos', 400, 1600, 'PEN'),
            ('Aspiradora robot', 'Pequeños electrodomésticos', 700, 2200, 'PEN'),
        ],
        'variantes': ['Línea Hogar', 'Línea Pro'],
        'titulos': ['Equipamiento de cocina para {c}', 'Renovación de televisores - {c}',
                    'Climatización de oficinas - {c}', 'Lavandería industrial para {c}',
                    'Computadoras para {c}', 'Equipamiento de habitaciones - {c}',
                    'Refrigeración para {c}', 'Compra corporativa de electrodomésticos - {c}'],
        'monto': (3000, 180000), 'usd': 0.0, 'cantidad': (1, 120),
    },
    {
        'tenant_id': 'ten_consultora', 'nombre': 'SoftNova Consultores',
        'rubro': 'Consultoría de software', 'dominio': 'softnova.pe',
        'demo': [('Andrea', 'Castillo', 'admin@softnova.pe', 'admin'),
                 ('Martín', 'Vargas', 'gerente@softnova.pe', 'gerente'),
                 ('Kevin', 'Ramos', 'vendedor@softnova.pe', 'vendedor')],
        'productos': [
            ('Hora de consultoría senior', 'Consultoría', 180, 320, 'PEN'),
            ('Hora de consultoría junior', 'Consultoría', 90, 160, 'PEN'),
            ('Desarrollo de aplicación web (sprint)', 'Desarrollo', 18000, 42000, 'PEN'),
            ('Desarrollo de app móvil (sprint)', 'Desarrollo', 22000, 48000, 'PEN'),
            ('Integración con ERP', 'Integración', 25000, 90000, 'PEN'),
            ('Migración a la nube', 'Nube', 30000, 120000, 'PEN'),
            ('Soporte mensual 8x5', 'Soporte', 3500, 9000, 'PEN'),
            ('Soporte mensual 24x7', 'Soporte', 9000, 22000, 'PEN'),
            ('Auditoría de seguridad', 'Seguridad', 15000, 60000, 'PEN'),
            ('Capacitación in-house (día)', 'Capacitación', 2500, 6500, 'PEN'),
            ('Tablero de analítica de datos', 'Datos', 12000, 45000, 'PEN'),
            ('Licencia SaaS por usuario (mes)', 'Licencias', 40, 120, 'PEN'),
            ('Cloud architecture assessment', 'Nube', 8000, 30000, 'USD'),
            ('Data platform implementation', 'Datos', 25000, 90000, 'USD'),
            ('Managed services (monthly)', 'Soporte', 3000, 12000, 'USD'),
            ('Software license (annual)', 'Licencias', 1200, 9000, 'USD'),
            ('Pentesting service', 'Seguridad', 6000, 25000, 'USD'),
            ('Dedicated developer (monthly)', 'Desarrollo', 4500, 9500, 'USD'),
        ],
        'variantes': ['Estándar', 'Avanzado'],
        'titulos': ['Implementación de ERP para {c}', 'App de ventas para {c}',
                    'Migración a la nube - {c}', 'Soporte anual de sistemas - {c}',
                    'Tablero de indicadores para {c}', 'Auditoría de seguridad - {c}',
                    'Portal web para {c}', 'Integración de sistemas - {c}'],
        'monto': (8000, 400000), 'usd': 0.3, 'cantidad': (1, 24),
    },
]

PLANTILLAS_AVISO = {  # copia de servicios/notificaciones/src/ProcesarEventos.py
    'usuario.creado': ('Bienvenido al CRM', 'Hola {nombre}, tu cuenta con rol {rol} ya está activa.',
                       ['usuario_id']),
    'cliente.creado': ('Nuevo cliente asignado',
                       'Se registró el cliente {nombre} y quedaste como responsable.',
                       ['responsable_id']),
    'oportunidad.creada': ('Nueva oportunidad',
                           'Se creó la oportunidad "{titulo}" por {monto_estimado}.',
                           ['responsable_id']),
    'oportunidad.etapa_cambiada': ('Oportunidad actualizada',
                                   'La oportunidad {oportunidad_id} pasó de {etapa_anterior} a {etapa_nueva}.',
                                   ['responsable_id']),
    'oportunidad.ganada': ('Oportunidad ganada', 'Se ganó la oportunidad "{titulo}" por {monto_estimado}.',
                           ['responsable_id', 'rol:gerente']),
    'oportunidad.perdida': ('Oportunidad perdida',
                            'La oportunidad {oportunidad_id} se perdió. Motivo: {motivo_perdida}.',
                            ['responsable_id', 'rol:gerente']),
    'cotizacion.enviada': ('Cotización enviada',
                           'La cotización {cotizacion_id} por {total} fue enviada al cliente.',
                           ['creada_por']),
    'cotizacion.aceptada': ('Cotización aceptada',
                            'El cliente aceptó la cotización {cotizacion_id} por {total}.',
                            ['rol:gerente']),
    'cotizacion.rechazada': ('Cotización rechazada', 'El cliente rechazó la cotización {cotizacion_id}.',
                             ['creada_por']),
    'actividad.completada': ('Actividad completada', 'Se completó la actividad {actividad_id}.',
                             ['responsable_id']),
}


# --------------------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------------------

class Secuencia:
    """Identificadores secuenciales con prefijo, únicos en todo el sistema (usr_000001...)."""

    def __init__(self):
        self.contadores = {}

    def __call__(self, prefijo):
        self.contadores[prefijo] = self.contadores.get(prefijo, 0) + 1
        return f'{prefijo}_{self.contadores[prefijo]:06d}'


def iso(fecha):
    return fecha.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sin_tildes(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')


def numero(valor):
    """Entero si no tiene decimales; si no, redondeado a 2 decimales (así lo devuelven las APIs)."""
    valor = round(valor, 2)
    return int(valor) if valor == int(valor) else valor


def ajustar_conteo(lista, objetivo, extra, sobrante):
    """Lleva una lista de cantidades a sumar exactamente `objetivo`."""
    total = sum(lista)
    while total < objetivo:
        i = extra()
        lista[i] += 1
        total += 1
    while total > objetivo:
        i = sobrante()
        if lista[i] > 1:
            lista[i] -= 1
            total -= 1
    return lista


class Generador:
    def __init__(self, por_tenant, semilla):
        self.n = por_tenant
        self.rng = random.Random(semilla)
        self.id = Secuencia()
        self.tablas = {tabla: [] for tabla in SERVICIO_DE_TABLA}
        self.correos = set()
        self.documentos = set()
        # Un solo hash para todos los usuarios ficticios: PBKDF2 con 600,000 iteraciones tarda
        # ~0.5 s por contraseña, así que 30,000 hashes distintos tomarían horas. Es un atajo
        # aceptable solo para datos de prueba: todos comparten contraseña y sal.
        self.hash_demo = crear_hash(CONTRASENA_DEMO)

    # ---------------------------------------------------------------- utilidades aleatorias
    def fecha_entre(self, desde, hasta):
        if hasta <= desde:
            return desde
        segundos = int((hasta - desde).total_seconds())
        return desde + timedelta(seconds=self.rng.randint(0, segundos))

    def hora_laboral(self, fecha):
        """Mueve una fecha a horario laboral de Lima (8:00-19:00, UTC-5)."""
        return fecha.replace(hour=self.rng.randint(13, 23), minute=self.rng.choice([0, 15, 30, 45]),
                             second=0)

    def hexa(self):
        return f'{self.rng.getrandbits(128):032x}'

    def persona(self):
        return self.rng.choice(NOMBRES), f'{self.rng.choice(APELLIDOS)} {self.rng.choice(APELLIDOS)}'

    def telefono(self):
        return f'9{self.rng.randint(10_000_000, 99_999_999)}'

    def documento(self, tipo):
        while True:
            if tipo == 'empresa':
                doc = f'20{self.rng.randint(100_000_000, 999_999_999)}'
            else:
                doc = f'{self.rng.randint(10_000_000, 79_999_999)}'
            if doc not in self.documentos:
                self.documentos.add(doc)
                return doc

    def correo_unico(self, nombre, apellidos, dominio):
        base = sin_tildes(f'{nombre}.{apellidos.split()[0]}').lower().replace(' ', '')
        correo, n = f'{base}@{dominio}', 1
        while correo in self.correos:
            n += 1
            correo = f'{base}{n}@{dominio}'
        self.correos.add(correo)
        return correo

    # ---------------------------------------------------------------- generación por tenant
    def generar(self):
        for tenant in TENANTS:
            contexto = {'tenant': tenant}
            self.tenant(contexto)
            self.usuarios(contexto)
            self.clientes(contexto)
            self.oportunidades(contexto)
            self.productos(contexto)
            self.cotizaciones(contexto)
            self.actividades(contexto)
            self.notificaciones(contexto)
        return self.tablas

    def tenant(self, ctx):
        t = ctx['tenant']
        fecha = iso(INICIO - timedelta(days=3))
        self.tablas['t_tenants'].append({
            'tenant_id': t['tenant_id'], 'nombre': t['nombre'],
            'nombre_normalizado': ' '.join(t['nombre'].lower().split()), 'rubro': t['rubro'],
            'estado': 'activo', 'fecha_creacion': fecha, 'fecha_actualizacion': fecha})
        self.tablas['t_tenants_locks'].append({
            'nombre_normalizado': ' '.join(t['nombre'].lower().split()), 'fecha_creacion': fecha})

    def usuarios(self, ctx):
        t = ctx['tenant']
        usuarios = []
        for i in range(self.n):
            if i < len(t['demo']):
                nombre, apellidos, correo, rol = t['demo'][i]
                self.correos.add(correo)
            else:
                nombre, apellidos = self.persona()
                correo = self.correo_unico(nombre, apellidos, t['dominio'])
                rol = 'gerente' if i < GERENTES_POR_TENANT + 2 else 'vendedor'
            fecha = INICIO - timedelta(days=3) if i == 0 else self.fecha_entre(INICIO, AHORA - timedelta(days=20))
            usuarios.append({
                'tenant_id': t['tenant_id'], 'usuario_id': self.id('usr'),
                'nombre': f'{nombre} {apellidos}', 'correo': correo,
                'contrasena_hash': self.hash_demo, 'rol': rol, 'estado': 'activo',
                'fecha_creacion': iso(fecha), 'fecha_actualizacion': iso(fecha)})
        demo_vendedor = usuarios[2]
        vendedores = [u for u in usuarios if u['rol'] == 'vendedor' and u is not demo_vendedor]
        cartera = [demo_vendedor] + vendedores[:VENDEDORES_CON_CARTERA - 1]
        ids_cartera = {u['usuario_id'] for u in cartera}
        # Gerentes y vendedores con cartera existen antes que los clientes que atienden
        for u in usuarios[1:]:
            if u['rol'] == 'gerente' or u['usuario_id'] in ids_cartera:
                fecha = iso(self.fecha_entre(INICIO - timedelta(days=3), INICIO - timedelta(hours=1)))
                u['fecha_creacion'] = u['fecha_actualizacion'] = fecha
        # 3 % de usuarios inactivos, nunca de demo ni con cartera
        for u in usuarios[len(t['demo']):]:
            if u['usuario_id'] not in ids_cartera and self.rng.random() < 0.03:
                u['estado'] = 'inactivo'
        for u in usuarios:
            self.tablas['t_usuarios'].append(u)
            self.tablas['t_correos_locks'].append(
                {'correo': u['correo'], 'tenant_id': u['tenant_id'], 'usuario_id': u['usuario_id']})
        ctx['usuarios'] = usuarios
        ctx['demo'] = usuarios[:3]
        ctx['cartera'] = cartera
        ctx['gerentes'] = [u for u in usuarios if u['rol'] == 'gerente' and u['estado'] == 'activo']
        # El vendedor demo recibe una cartera ~3 veces mayor que el promedio, para la demo
        ctx['peso_cartera'] = [3.0] + [1.0] * (len(cartera) - 1)

    def responsable(self, ctx):
        return self.rng.choices(ctx['cartera'], weights=ctx['peso_cartera'])[0]['usuario_id']

    def clientes(self, ctx):
        t = ctx['tenant']
        clientes = []
        for _ in range(self.n):
            tipo = 'empresa' if self.rng.random() < 0.75 else 'persona'
            industria = self.rng.choice(INDUSTRIAS)
            if tipo == 'empresa':
                nucleo = self.rng.choice(NUCLEOS_EMPRESA)
                nombre = f'{TIPOS_EMPRESA[industria]} {nucleo} {self.rng.choice(SUFIJOS_EMPRESA)}'
                dominio = sin_tildes(nucleo).lower() + self.rng.choice(['.pe', '.com.pe', '.com'])
                correo = f'{self.rng.choice(["ventas", "compras", "contacto", "info"])}@{dominio}'
            else:
                nombres, apellidos = self.persona()
                nombre = f'{nombres} {apellidos}'
                correo = sin_tildes(f'{nombres}.{apellidos.split()[0]}').lower() + '@gmail.com'
            fecha = self.fecha_entre(INICIO, AHORA - timedelta(days=2))
            estado = self.rng.choices(['prospecto', 'activo', 'inactivo'], weights=[30, 60, 10])[0]
            clientes.append({
                'tenant_id': t['tenant_id'], 'cliente_id': self.id('cli'), 'nombre': nombre,
                'tipo': tipo, 'documento': self.documento(tipo), 'correo': correo,
                'telefono': self.telefono(), 'industria': industria if tipo == 'empresa' else '',
                'ciudad': self.rng.choice(CIUDADES), 'estado': estado,
                'responsable_id': self.responsable(ctx), 'fecha_creacion': iso(fecha),
                'fecha_actualizacion': iso(fecha)})
        # Contactos: 1 o 2 por cliente; el 90 % de los clientes tiene contacto principal
        for c in clientes:
            for k in range(self.rng.choice([1, 1, 2])):
                nombres, apellidos = self.persona()
                principal = k == 0 and self.rng.random() < 0.9
                contacto = {
                    'tenant_id': t['tenant_id'], 'contacto_id': self.id('con'),
                    'cliente_id': c['cliente_id'], 'nombre': f'{nombres} {apellidos}',
                    'cargo': self.rng.choice(CARGOS) if c['tipo'] == 'empresa' else 'Titular',
                    'correo': sin_tildes(f'{nombres}.{apellidos.split()[0]}').lower() + '@' + (
                        c['correo'].split('@')[1] if c['tipo'] == 'empresa' else 'gmail.com'),
                    'telefono': self.telefono(), 'es_principal': principal,
                    'fecha_creacion': c['fecha_creacion']}
                if principal:
                    c['contacto_principal_id'] = contacto['contacto_id']
                self.tablas['t_contactos'].append(contacto)
        self.tablas['t_clientes'].extend(clientes)
        ctx['clientes'] = clientes

    def camino(self, etapa_final):
        """Etapas recorridas desde 'nueva': solo avanzan y pueden saltarse."""
        if etapa_final == 'nueva':
            return ['nueva']
        if etapa_final == 'perdida':
            ultima_abierta = self.rng.choice(ABIERTAS)
            intermedias = [e for e in ABIERTAS[1:ABIERTAS.index(ultima_abierta) + 1]]
        else:
            limite = 4 if etapa_final == 'ganada' else ETAPAS.index(etapa_final)
            intermedias = [e for e in ETAPAS[1:limite] if self.rng.random() < 0.75]
        return ['nueva'] + intermedias + [etapa_final]

    def oportunidades(self, ctx):
        t = ctx['tenant']
        vigentes = [c for c in ctx['clientes'] if c['estado'] != 'inactivo']
        oportunidades = []
        etapas = list(PESO_ETAPA)
        for _ in range(self.n):
            etapa = self.rng.choices(etapas, weights=[PESO_ETAPA[e] for e in etapas])[0]
            # Las oportunidades abiertas solo van a clientes vigentes; las cerradas, a cualquiera
            cliente = self.rng.choice(vigentes if etapa in ABIERTAS else ctx['clientes'])
            creado_cliente = datetime.fromisoformat(cliente['fecha_creacion'].replace('Z', '+00:00'))
            creacion = self.fecha_entre(creado_cliente, AHORA - timedelta(days=1))
            camino = self.camino(etapa)
            # Fechas de cada cambio, crecientes y antes de AHORA
            fechas, actual = [], creacion
            for _ in camino[1:]:
                margen = (AHORA - actual) / (len(camino) + 1)
                actual = self.fecha_entre(actual + timedelta(minutes=30), actual + max(margen, timedelta(hours=1)))
                fechas.append(min(actual, AHORA - timedelta(minutes=5)))
            moneda = 'USD' if self.rng.random() < t['usd'] else 'PEN'
            minimo, maximo = t['monto']
            monto = self.rng.randrange(minimo, maximo, 500)
            if moneda == 'USD':
                monto = self.rng.randrange(minimo // 3, maximo // 3, 100)
            ultima = fechas[-1] if fechas else creacion
            o = {
                'tenant_id': t['tenant_id'], 'oportunidad_id': self.id('opo'),
                'cliente_id': cliente['cliente_id'], 'cliente_nombre': cliente['nombre'],
                'titulo': self.rng.choice(t['titulos']).format(c=cliente['nombre']),
                'monto_estimado': monto, 'moneda': moneda, 'etapa': etapa,
                'probabilidad': PROBABILIDAD[etapa],
                'fecha_cierre_estimada': iso(self.hora_laboral(creacion + timedelta(days=self.rng.randint(20, 120)))),
                'responsable_id': cliente['responsable_id'],
                'fecha_creacion': iso(creacion), 'fecha_actualizacion': iso(ultima)}
            if etapa == 'perdida':
                o['motivo_perdida'] = self.rng.choice(MOTIVOS_PERDIDA)
            o['_camino'], o['_fechas'] = camino, fechas
            oportunidades.append(o)
        ctx['oportunidades'] = oportunidades

    def productos(self, ctx):
        t = ctx['tenant']
        productos = []
        for nombre, categoria, minimo, maximo, moneda in t['productos']:
            for variante in t['variantes']:
                fecha = iso(self.fecha_entre(INICIO - timedelta(days=2), INICIO + timedelta(days=20)))
                productos.append({
                    'tenant_id': t['tenant_id'], 'producto_id': self.id('pro'),
                    'nombre': f'{nombre} - {variante}',
                    'descripcion': f'{nombre} en su modalidad {variante.lower()}.',
                    'categoria': categoria,
                    'precio': numero(self.rng.uniform(minimo, maximo)),
                    'moneda': moneda, 'estado': 'activo',
                    'fecha_creacion': fecha, 'fecha_actualizacion': fecha})
        # Un 5 % del catálogo descontinuado (no se usa en cotizaciones nuevas)
        for p in self.rng.sample(productos, max(1, len(productos) // 20)):
            p['estado'] = 'inactivo'
        self.tablas['t_productos'].extend(productos)
        ctx['productos'] = {m: [p for p in productos if p['estado'] == 'activo' and p['moneda'] == m]
                            for m in ('PEN', 'USD')}

    def cotizaciones(self, ctx):
        """Cotizaciones coherentes con la etapa de su oportunidad; exactamente N por tenant."""
        ops = ctx['oportunidades']
        # Oportunidades ganadas: 70 % por cotización aceptada (cambio hecho por 'sistema')
        for o in ops:
            o['_por_cotizacion'] = o['etapa'] == 'ganada' and self.rng.random() < 0.7
        # Solo se cotiza lo que llegó al menos a 'propuesta' (las perdidas en etapas tempranas, no)
        elegibles = [i for i, o in enumerate(ops)
                     if o['etapa'] in ('propuesta', 'en_negociacion') or o['_por_cotizacion']
                     or (o['etapa'] == 'perdida' and {'propuesta', 'en_negociacion'} & set(o['_camino']))]
        cantidades = [0] * len(ops)
        for i in elegibles:
            cantidades[i] = self.rng.choice([1, 1, 2]) if ops[i]['etapa'] != 'en_negociacion' else self.rng.choice([1, 2, 2])
        ajustar_conteo(cantidades, self.n, extra=lambda: self.rng.choice(elegibles),
                       sobrante=lambda: self.rng.choice(elegibles))

        for o, cantidad in zip(ops, cantidades):
            if not cantidad:
                continue
            # Fecha desde la que tiene sentido cotizar: cuando llegó a 'propuesta' o más
            desde = datetime.fromisoformat(o['fecha_creacion'].replace('Z', '+00:00'))
            for etapa, fecha in zip(o['_camino'][1:], o['_fechas']):
                if ETAPAS.index(etapa) >= 2:
                    desde = fecha - timedelta(days=self.rng.randint(1, 5))
                    break
            cierre = o['_fechas'][-1] if o['etapa'] in ('ganada', 'perdida') else AHORA
            desde = max(desde, datetime.fromisoformat(o['fecha_creacion'].replace('Z', '+00:00')))
            fechas = sorted(self.fecha_entre(desde, cierre - timedelta(minutes=20)) for _ in range(cantidad))
            if o['_por_cotizacion']:
                # La aceptación debe ocurrir después del cambio de etapa anterior a 'ganada'
                penultimo = (o['_fechas'][-2] if len(o['_fechas']) > 1
                             else datetime.fromisoformat(o['fecha_creacion'].replace('Z', '+00:00')))
                fechas[-1] = max(fechas[-1], penultimo + timedelta(minutes=1))
            for k, fecha in enumerate(fechas):
                ultima = k == cantidad - 1
                if not ultima:
                    estado = 'rechazada'  # versiones anteriores que el cliente no aceptó
                elif o['etapa'] == 'ganada':
                    estado = 'aceptada'
                elif o['etapa'] == 'perdida':
                    estado = 'rechazada'
                elif o['etapa'] == 'propuesta':
                    estado = self.rng.choice(['borrador', 'enviada', 'enviada'])
                else:
                    estado = 'enviada'
                self.cotizacion(ctx, o, fecha, estado, fechas[k + 1] if not ultima else cierre)
            if o['_por_cotizacion']:
                # El cierre lo hizo el consumidor de cotizacion.aceptada, después de la respuesta
                aceptada = ctx['ultima_cotizacion']
                o['_fechas'][-1] = datetime.fromisoformat(aceptada['fecha_resultado_aceptacion'].replace('Z', '+00:00')) + timedelta(seconds=self.rng.randint(2, 40))
                o['fecha_actualizacion'] = iso(o['_fechas'][-1])

    def cotizacion(self, ctx, o, fecha, estado, limite):
        t = ctx['tenant']
        catalogo = ctx['productos'][o['moneda']]
        items = []
        for p in self.rng.sample(catalogo, self.rng.randint(1, min(5, len(catalogo)))):
            cantidad = self.rng.randint(*t['cantidad'])
            items.append({'producto_id': p['producto_id'], 'nombre_producto': p['nombre'],
                          'cantidad': cantidad, 'precio_unitario': p['precio'],
                          'subtotal': numero(cantidad * p['precio'])})
        total = numero(sum(i['subtotal'] for i in items))
        abierta = estado in ('borrador', 'enviada')
        # Las cotizaciones vigentes de oportunidades abiertas vencen en el futuro, para la demo
        vencimiento = (AHORA + timedelta(days=self.rng.randint(7, 45)) if abierta
                       else fecha + timedelta(days=15))
        c = {'tenant_id': t['tenant_id'], 'cotizacion_id': self.id('cot'),
             'oportunidad_id': o['oportunidad_id'], 'cliente_id': o['cliente_id'],
             'estado': estado, 'items': items, 'total': total, 'moneda': o['moneda'],
             'fecha_vencimiento': iso(vencimiento), 'creada_por': o['responsable_id'],
             'fecha_creacion': iso(fecha), 'fecha_actualizacion': iso(fecha)}
        if estado != 'borrador':
            envio = self.fecha_entre(fecha + timedelta(minutes=5), min(fecha + timedelta(days=2), limite - timedelta(minutes=10)))
            c['fecha_envio'] = iso(envio)
            c['fecha_actualizacion'] = iso(envio)
            respuesta = self.fecha_entre(envio + timedelta(minutes=5), min(envio + timedelta(days=10), limite - timedelta(minutes=2)))
            if estado == 'rechazada':
                c.update({'fecha_respuesta': iso(respuesta), 'respondida_por': o['responsable_id'],
                          'fecha_actualizacion': iso(respuesta)})
                if self.rng.random() < 0.7:
                    c['motivo_rechazo'] = self.rng.choice(MOTIVOS_RECHAZO)
            elif estado == 'aceptada':
                solicitud = f'sol_{self.hexa()}'
                resultado = respuesta + timedelta(seconds=self.rng.randint(3, 50))
                c.update({'solicitud_aceptacion_id': solicitud, 'resultado_solicitud_id': solicitud,
                          'respondida_por': o['responsable_id'], 'resultado_aceptacion': '',
                          'fecha_respuesta': iso(resultado),
                          'fecha_resultado_aceptacion': iso(resultado),
                          'fecha_actualizacion': iso(resultado)})
        self.tablas['t_cotizaciones'].append(c)
        ctx['ultima_cotizacion'] = c

    def historial(self, ctx):
        """Se escribe después de las cotizaciones porque el cierre por cotización ajusta fechas."""
        for o in ctx['oportunidades']:
            camino, fechas = o.pop('_camino'), o.pop('_fechas')
            por_cotizacion = o.pop('_por_cotizacion')
            for k, (anterior, nueva) in enumerate(zip(camino, camino[1:])):
                sistema = por_cotizacion and nueva == 'ganada'
                self.tablas['t_historial_etapas'].append({
                    'tenant_id': o['tenant_id'], 'historial_id': self.id('his'),
                    'oportunidad_id': o['oportunidad_id'], 'etapa_anterior': anterior,
                    'etapa_nueva': nueva, 'usuario_id': 'sistema' if sistema else o['responsable_id'],
                    'fecha_cambio': iso(fechas[k])})
            o['_cierre'] = fechas[-1] if o['etapa'] in ('ganada', 'perdida') else None
            o['_cambios'] = list(zip(camino, camino[1:], fechas))

    def actividades(self, ctx):
        t = ctx['tenant']
        self.historial(ctx)
        ops = ctx['oportunidades']
        clientes = {c['cliente_id']: c for c in ctx['clientes']}
        titulos = {
            'llamada': ['Llamar a {k} para seguimiento', 'Confirmar requerimiento con {k}',
                        'Llamada de presentación a {k}'],
            'reunion': ['Reunión de seguimiento con {k}', 'Presentar propuesta a {k}',
                        'Visita comercial a {k}'],
            'correo': ['Enviar propuesta a {k}', 'Enviar información solicitada a {k}',
                       'Correo de seguimiento a {k}'],
            'tarea': ['Preparar cotización para {k}', 'Actualizar datos de {k}',
                      'Revisar condiciones comerciales de {k}'],
        }
        actividades = []
        for _ in range(self.n):
            o = self.rng.choice(ops) if self.rng.random() < 0.75 else None
            cliente = clientes[o['cliente_id']] if o else self.rng.choice(ctx['clientes'])
            tipo = self.rng.choice(list(titulos))
            inicio = datetime.fromisoformat((o or cliente)['fecha_creacion'].replace('Z', '+00:00'))
            if o and o['etapa'] == 'perdida':
                fin = o['_cierre']  # nada puede quedar pendiente después de perderla
            else:
                fin = AHORA + timedelta(days=45)
            programada = self.hora_laboral(self.fecha_entre(inicio + timedelta(hours=2), fin))
            perdida = o is not None and o['etapa'] == 'perdida'
            if perdida:
                programada = max(min(programada, o['_cierre'] - timedelta(minutes=10)), inicio)
            if perdida:
                # Lo que estaba pendiente al perderse la oportunidad se canceló automáticamente
                estado = 'completada' if self.rng.random() < 0.6 else 'cancelada'
            elif programada > AHORA:
                estado = 'pendiente'
            else:
                estado = self.rng.choices(['completada', 'cancelada', 'pendiente'], weights=[85, 8, 7])[0]
            automatica = o is not None and self.rng.random() < 0.25
            creacion = min(self.fecha_entre(inicio, programada), AHORA - timedelta(minutes=10))
            actualizacion = creacion
            if estado != 'pendiente':
                actualizacion = min(max(programada, creacion) + timedelta(hours=self.rng.randint(0, 30)),
                                    AHORA - timedelta(minutes=1))
                if perdida and estado == 'cancelada':
                    actualizacion = o['_cierre'] + timedelta(seconds=self.rng.randint(5, 90))
                elif perdida:
                    actualizacion = max(min(actualizacion, o['_cierre'] - timedelta(minutes=1)), creacion)
            a = {'tenant_id': t['tenant_id'], 'actividad_id': self.id('act'), 'tipo': tipo,
                 'titulo': self.rng.choice(titulos[tipo]).format(k=cliente['nombre']),
                 'descripcion': ('Seguimiento de "' + o['titulo'] + '"') if o else '',
                 'cliente_id': cliente['cliente_id'],
                 'responsable_id': o['responsable_id'] if o else cliente['responsable_id'],
                 'fecha_programada': iso(programada), 'estado': estado,
                 'origen': 'automatica' if automatica else 'manual',
                 'fecha_creacion': iso(creacion), 'fecha_actualizacion': iso(actualizacion),
                 'version': 1 if estado == 'pendiente' else 2}
            if o:
                a['oportunidad_id'] = o['oportunidad_id']
            actividades.append(a)
        self.tablas['t_actividades'].extend(actividades)
        ctx['actividades'] = actividades
        # Barrera de Actividades: impide crear pendientes en oportunidades perdidas
        for o in ops:
            if o['etapa'] == 'perdida':
                self.tablas['t_oportunidades_control_actividades'].append({
                    'tenant_id': t['tenant_id'], 'oportunidad_id': o['oportunidad_id'],
                    'perdida': True, 'fecha_actualizacion': iso(o['_cierre'] + timedelta(seconds=3))})

    def notificaciones(self, ctx):
        """Avisos tal como los habría guardado el consumidor a partir de eventos reales."""
        t = ctx['tenant']
        tid = t['tenant_id']
        eventos = []  # (fecha, tipo, datos)
        for u in ctx['usuarios']:
            eventos.append((u['fecha_creacion'], 'usuario.creado',
                            {'usuario_id': u['usuario_id'], 'nombre': u['nombre'], 'rol': u['rol']}))
        for c in ctx['clientes']:
            eventos.append((c['fecha_creacion'], 'cliente.creado',
                            {'nombre': c['nombre'], 'responsable_id': c['responsable_id']}))
        for o in ctx['oportunidades']:
            base = {'oportunidad_id': o['oportunidad_id'], 'titulo': o['titulo'],
                    'monto_estimado': o['monto_estimado'], 'responsable_id': o['responsable_id']}
            eventos.append((o['fecha_creacion'], 'oportunidad.creada', base))
            for anterior, nueva, fecha in o['_cambios']:
                if nueva == 'ganada':
                    eventos.append((iso(fecha), 'oportunidad.ganada', base))
                elif nueva == 'perdida':
                    eventos.append((iso(fecha), 'oportunidad.perdida',
                                    {**base, 'motivo_perdida': o['motivo_perdida']}))
                else:
                    eventos.append((iso(fecha), 'oportunidad.etapa_cambiada',
                                    {**base, 'etapa_anterior': anterior, 'etapa_nueva': nueva}))
        for c in (c for c in self.tablas['t_cotizaciones'] if c['tenant_id'] == tid):
            datos = {'cotizacion_id': c['cotizacion_id'], 'total': c['total'], 'creada_por': c['creada_por']}
            if 'fecha_envio' in c:
                eventos.append((c['fecha_envio'], 'cotizacion.enviada', datos))
            if c['estado'] == 'rechazada':
                eventos.append((c['fecha_respuesta'], 'cotizacion.rechazada', datos))
            elif c['estado'] == 'aceptada':
                eventos.append((c['fecha_resultado_aceptacion'], 'cotizacion.aceptada', datos))
        for a in ctx['actividades']:
            if a['estado'] == 'completada':
                eventos.append((a['fecha_actualizacion'], 'actividad.completada',
                                {'actividad_id': a['actividad_id'], 'responsable_id': a['responsable_id']}))

        # Primero todo lo que afecta a los usuarios demo; luego relleno aleatorio priorizando
        # lo reciente, hasta llegar exactamente a N avisos (un evento puede generar 2 avisos).
        demo = {u['usuario_id'] for u in ctx['demo']}

        def destinos(tipo, datos):
            return [d if d.startswith('rol:') else datos[d] for d in PLANTILLAS_AVISO[tipo][2]]

        reciente = iso(AHORA - timedelta(days=60))

        def prioridad(evento):
            fecha, tipo, datos = evento
            es_demo = any(d in demo for d in destinos(tipo, datos))
            # Orden aleatorio, con ventaja para los eventos de los últimos 60 días
            return (0 if es_demo else 1, self.rng.random() - (0.5 if fecha >= reciente else 0))

        eventos.sort(key=prioridad)
        avisos = []
        for fecha, tipo, datos in eventos:
            nuevos = self.avisos(tid, fecha, tipo, datos)
            if len(avisos) + len(nuevos) > self.n:
                nuevos = nuevos[:self.n - len(avisos)]
            avisos.extend(nuevos)
            if len(avisos) == self.n:
                break
        self.tablas['t_notificaciones'].extend(avisos)

        # Lecturas: los avisos con más de 7 días los leyó su destinatario en un 60 %;
        # los dirigidos al rol gerente, el gerente demo los leyó en un 50 %.
        gerente_demo = ctx['demo'][1]['usuario_id']
        limite = iso(AHORA - timedelta(days=7))
        for aviso in avisos:
            if aviso['fecha_creacion'] > limite:
                continue
            lector = aviso.get('usuario_destino_id') or gerente_demo
            probabilidad = 0.6 if 'usuario_destino_id' in aviso else 0.5
            if self.rng.random() < probabilidad:
                lectura = datetime.fromisoformat(aviso['fecha_creacion'].replace('Z', '+00:00')) + timedelta(hours=self.rng.randint(1, 72))
                self.tablas['t_lecturas_notificaciones'].append({
                    'tenant_id': tid, 'lectura_id': f"{aviso['notificacion_id']}#{lector}",
                    'notificacion_id': aviso['notificacion_id'], 'usuario_id': lector,
                    'fecha_lectura': iso(min(lectura, AHORA - timedelta(minutes=1)))})
        for o in ctx['oportunidades']:
            o.pop('_cierre')
            o.pop('_cambios')
        self.tablas['t_oportunidades'].extend(ctx['oportunidades'])

    def avisos(self, tenant_id, fecha_evento, tipo, datos):
        titulo, plantilla, destinos = PLANTILLAS_AVISO[tipo]
        evento_id = f'evt_{self.hexa()}'
        fecha = iso(datetime.fromisoformat(fecha_evento.replace('Z', '+00:00')) + timedelta(seconds=self.rng.randint(30, 120)))
        fecha = min(fecha, iso(AHORA))
        mensaje = plantilla.format_map(datos)
        resultado = []
        for destino in destinos:
            item = {'tenant_id': tenant_id, 'tipo': tipo, 'titulo': titulo, 'mensaje': mensaje,
                    'evento_id': evento_id, 'fecha_creacion': fecha}
            if destino.startswith('rol:'):
                item['rol_destino'] = destino[4:]
                item['destino'] = f'{tenant_id}#rol#{destino[4:]}'
            else:
                item['usuario_destino_id'] = datos[destino]
                item['destino'] = f'{tenant_id}#usr#{datos[destino]}'
            huella = hashlib.sha256(f"{tenant_id}|{evento_id}|{item['destino']}".encode()).hexdigest()[:32]
            item['notificacion_id'] = f'not_{huella}'
            item['orden'] = f"{fecha}#{item['notificacion_id']}"
            resultado.append(item)
        return resultado


# --------------------------------------------------------------------------------------
# Escritura de archivos
# --------------------------------------------------------------------------------------

def escribir(tablas, salida, tamano_parte):
    resumen = {}
    for tabla, registros in tablas.items():
        servicio = SERVICIO_DE_TABLA[tabla]
        carpeta = salida / servicio / 'importaciones' / tabla
        carpeta.mkdir(parents=True, exist_ok=True)
        for viejo in carpeta.glob('parte_*.jsonl'):
            viejo.unlink()
        for parte, inicio in enumerate(range(0, len(registros), tamano_parte), start=1):
            with open(carpeta / f'parte_{parte:04d}.jsonl', 'w', encoding='utf-8', newline='\n') as f:
                for registro in registros[inicio:inicio + tamano_parte]:
                    f.write(json.dumps(registro, ensure_ascii=False) + '\n')
        por_tenant = {}
        for r in registros:
            clave = r.get('tenant_id', 'global')
            por_tenant[clave] = por_tenant.get(clave, 0) + 1
        resumen[tabla] = {'servicio': servicio, 'total': len(registros), 'por_tenant': por_tenant}
    with open(salida / 'resumen.json', 'w', encoding='utf-8') as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    return resumen


def main():
    parser = argparse.ArgumentParser(description='Genera datos ficticios coherentes del CRM SaaS.')
    parser.add_argument('--por-tenant', type=int, default=10_000,
                        help='Registros por tenant en la tabla principal de cada servicio (defecto 10000)')
    parser.add_argument('--semilla', type=int, default=2032, help='Semilla aleatoria (defecto 2032)')
    parser.add_argument('--salida', type=Path, default=RAIZ / 'datos' / 'salida')
    parser.add_argument('--tamano-parte', type=int, default=5_000,
                        help='Registros por archivo .jsonl (defecto 5000)')
    args = parser.parse_args()
    if args.por_tenant < 100:
        parser.error('--por-tenant debe ser al menos 100')

    print(f'Generando {args.por_tenant:,} registros por tenant (semilla {args.semilla})...')
    tablas = Generador(args.por_tenant, args.semilla).generar()
    resumen = escribir(tablas, args.salida, args.tamano_parte)
    print(f'\n{"Tabla":40} {"Servicio":24} {"Total":>8}')
    for tabla, datos in resumen.items():
        print(f'{tabla:40} {datos["servicio"]:24} {datos["total"]:>8,}')
    print(f'\nArchivos en: {args.salida}')
    print(f'Contraseña de todos los usuarios ficticios: {CONTRASENA_DEMO}')


if __name__ == '__main__':
    main()