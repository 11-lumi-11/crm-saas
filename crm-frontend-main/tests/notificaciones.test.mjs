import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import vm from 'node:vm'

const source = await readFile(new URL('../src/notificacionesApi.js', import.meta.url), 'utf8')

async function cargar({ token = 'token-demo', status = 200, data = {}, fallaRed = false } = {}) {
  const llamadas = []
  const context = vm.createContext({
    URLSearchParams,
    localStorage: { getItem: () => token },
    fetch: async (url, opciones) => {
      llamadas.push({ url, opciones })
      if (fallaRed) throw new Error('sin red')
      return { ok: status < 400, status, json: async () => data }
    },
  })
  const modulo = new vm.SourceTextModule(source, {
    context,
    initializeImportMeta(meta) { meta.env = { VITE_NOTIFICACIONES_URL: 'https://notificaciones.example/' } },
  })
  await modulo.link(() => {})
  await modulo.evaluate()
  return { api: modulo.namespace.notificacionesApi, llamadas }
}

test('listar usa el token y conserva el filtro y el cursor', async () => {
  const { api, llamadas } = await cargar({ data: { notificaciones: [], siguiente: 'cursor' } })
  const datos = await api.listar({ siguiente: 'fecha#not_1', soloNoLeidas: true })
  const url = new URL(llamadas[0].url)
  assert.equal(url.searchParams.get('siguiente'), 'fecha#not_1')
  assert.equal(url.searchParams.get('solo_no_leidas'), 'true')
  assert.equal(llamadas[0].opciones.headers.Authorization, 'Bearer token-demo')
  assert.equal(datos.siguiente, 'cursor')
})

test('marcar lectura usa PUT y devuelve la respuesta', async () => {
  const { api, llamadas } = await cargar({ data: { notificacion_id: 'not_1', leida: true } })
  const datos = await api.marcarLeida('not_1')
  assert.equal(llamadas[0].url, 'https://notificaciones.example/notificaciones/not_1/leer')
  assert.equal(llamadas[0].opciones.method, 'PUT')
  assert.equal(datos.leida, true)
})

test('errores de permisos y de red no simulan una lectura exitosa', async () => {
  const prohibida = await cargar({ status: 404, data: { mensaje: 'La notificación no existe' } })
  await assert.rejects(prohibida.api.marcarLeida('not_ajena'), /no existe/)
  const sinRed = await cargar({ fallaRed: true })
  await assert.rejects(sinRed.api.listar(), /No se pudo conectar/)
  const sinSesion = await cargar({ token: null })
  await assert.rejects(sinSesion.api.listar(), /No se encontró la sesión/)
  assert.equal(sinSesion.llamadas.length, 0)
})
