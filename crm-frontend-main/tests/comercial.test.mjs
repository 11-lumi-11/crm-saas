import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import vm from 'node:vm'

const source = await readFile(new URL('../src/apiComercial.js', import.meta.url), 'utf8')

async function cargar({ token = 'token-demo', status = 200, data = {} } = {}) {
  const llamadas = []
  const context = vm.createContext({
    URLSearchParams,
    localStorage: { getItem: () => token },
    fetch: async (url, opciones) => {
      llamadas.push({ url, opciones })
      return { ok: status < 400, status, json: async () => data }
    },
  })
  const module = new vm.SourceTextModule(source, {
    context,
    initializeImportMeta(meta) { meta.env = { VITE_OPORTUNIDADES_URL: 'https://op.example', VITE_ACTIVIDADES_URL: 'https://act.example' } },
  })
  await module.link(() => {})
  await module.evaluate()
  return { ...module.namespace, llamadas }
}

test('crear oportunidad envía el cliente y el monto con token', async () => {
  const { oportunidadesApi, llamadas } = await cargar({ data: { oportunidad_id: 'opo_1' } })
  await oportunidadesApi.crear({ cliente_id: 'cli_1', titulo: 'Venta', monto_estimado: 300, moneda: 'PEN' })
  assert.equal(llamadas[0].url, 'https://op.example/oportunidades')
  assert.equal(llamadas[0].opciones.headers.Authorization, 'Bearer token-demo')
  assert.equal(JSON.parse(llamadas[0].opciones.body).monto_estimado, 300)
})

test('cambio a perdida incluye motivo y comunica errores reales', async () => {
  const { oportunidadesApi, llamadas } = await cargar({ status: 409, data: { mensaje: 'La oportunidad ya está cerrada' } })
  await assert.rejects(oportunidadesApi.etapa('opo_1', { etapa: 'perdida', motivo_perdida: 'Sin acuerdo' }), /ya está cerrada/)
  assert.equal(llamadas[0].url, 'https://op.example/oportunidades/opo_1/etapa')
  assert.equal(JSON.parse(llamadas[0].opciones.body).motivo_perdida, 'Sin acuerdo')
})

test('actividades conserva el filtro y el cursor opaco', async () => {
  const { actividadesApi, llamadas } = await cargar({ data: { actividades: [], siguiente: null } })
  await actividadesApi.listar({ responsable_id: 'usr_1', siguiente: 'abc+/=' })
  const url = new URL(llamadas[0].url)
  assert.equal(url.searchParams.get('responsable_id'), 'usr_1')
  assert.equal(url.searchParams.get('siguiente'), 'abc+/=')
  assert.equal(llamadas[0].opciones.headers.Authorization, 'Bearer token-demo')
})

test('completar usa la ruta real y no envía datos simulados', async () => {
  const { actividadesApi, llamadas } = await cargar({ data: { actividad: { estado: 'completada' } } })
  const datos = await actividadesApi.completar('act_1')
  assert.equal(llamadas[0].url, 'https://act.example/actividades/act_1/completar')
  assert.equal(llamadas[0].opciones.method, 'PUT')
  assert.equal(datos.actividad.estado, 'completada')
})

test('sin sesión no se consulta AWS', async () => {
  const { oportunidadesApi, llamadas } = await cargar({ token: null })
  await assert.rejects(oportunidadesApi.listar(), /No se encontró la sesión/)
  assert.equal(llamadas.length, 0)
})
