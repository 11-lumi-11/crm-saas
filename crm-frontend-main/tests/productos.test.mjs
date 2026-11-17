import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import vm from 'node:vm'
import { aplicarResultadoAceptacion } from '../src/aceptacionCotizacion.js'

const source = await readFile(new URL('../src/productosApi.js', import.meta.url), 'utf8')
async function cargar({ token = 'token-demo', status = 200, data = {} } = {}) {
  const llamadas = []
  const context = vm.createContext({ URLSearchParams, localStorage: { getItem: () => token },
    fetch: async (url, opciones) => { llamadas.push({ url, opciones }); return { ok: status < 400, status, json: async () => data } } })
  const modulo = new vm.SourceTextModule(source, { context,
    initializeImportMeta(meta) { meta.env = { VITE_PRODUCTOS_URL: 'https://productos.example/' } } })
  await modulo.link(() => {})
  await modulo.evaluate()
  return { ...modulo.namespace, llamadas }
}

test('crear producto envía precio numérico y token', async () => {
  const { productosApi, llamadas } = await cargar({ data: { producto_id: 'pro_1' } })
  await productosApi.crear({ nombre: 'Producto', precio: 100.5, moneda: 'PEN' })
  assert.equal(llamadas[0].url, 'https://productos.example/productos')
  assert.equal(llamadas[0].opciones.headers.Authorization, 'Bearer token-demo')
  assert.equal(JSON.parse(llamadas[0].opciones.body).precio, 100.5)
})

test('crear cotización conserva identificadores y cantidades', async () => {
  const { cotizacionesApi, llamadas } = await cargar({ data: { cotizacion_id: 'cot_1' } })
  await cotizacionesApi.crear({ oportunidad_id: 'opo_1', cliente_id: 'cli_1', moneda: 'PEN', items: [{ producto_id: 'pro_1', cantidad: 2 }] })
  const body = JSON.parse(llamadas[0].opciones.body)
  assert.equal(body.oportunidad_id, 'opo_1')
  assert.deepEqual(body.items, [{ producto_id: 'pro_1', cantidad: 2 }])
})

test('aceptar usa la solicitud real y errores no se presentan como éxito', async () => {
  const { cotizacionesApi, llamadas } = await cargar({ status: 409, data: { mensaje: 'La cotización ya venció' } })
  await assert.rejects(cotizacionesApi.aceptar('cot_1'), /ya venció/)
  assert.equal(llamadas[0].url, 'https://productos.example/cotizaciones/cot_1/aceptar')
  assert.equal(llamadas[0].opciones.method, 'PUT')
})

test('el resultado anterior no reemplaza una aceptación nueva pendiente', () => {
  const pendiente = { estado: 'aceptacion_pendiente', _solicitudAnterior: 'sol_anterior' }
  const vieja = { estado: 'enviada', solicitud_aceptacion_id: 'sol_anterior', resultado_solicitud_id: 'sol_anterior', resultado_aceptacion: 'Perdida' }
  assert.equal(aplicarResultadoAceptacion(pendiente, vieja), pendiente)
  const nueva = { estado: 'aceptada', solicitud_aceptacion_id: 'sol_nueva', resultado_solicitud_id: 'sol_nueva' }
  assert.equal(aplicarResultadoAceptacion(pendiente, nueva), nueva)
})

test('solo se muestra el rechazo cuando corresponde a la solicitud', () => {
  const pendiente = { estado: 'aceptacion_pendiente' }
  const incoherente = { estado: 'enviada', solicitud_aceptacion_id: 'sol_2', resultado_solicitud_id: 'sol_1' }
  assert.equal(aplicarResultadoAceptacion(pendiente, incoherente), pendiente)
  const denegada = { estado: 'enviada', solicitud_aceptacion_id: 'sol_2', resultado_solicitud_id: 'sol_2', resultado_aceptacion: 'Oportunidad perdida' }
  assert.equal(aplicarResultadoAceptacion(pendiente, denegada), denegada)
})

test('la paginación conserva el cursor y sin sesión no consulta', async () => {
  const { cotizacionesApi, llamadas } = await cargar({ data: { cotizaciones: [], siguiente: null } })
  await cotizacionesApi.listar('cot_1')
  assert.equal(new URL(llamadas[0].url).searchParams.get('siguiente'), 'cot_1')
  const sinSesion = await cargar({ token: null })
  await assert.rejects(sinSesion.productosApi.listar(), /No se encontró la sesión/)
  assert.equal(sinSesion.llamadas.length, 0)
})
