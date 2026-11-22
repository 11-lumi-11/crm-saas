import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import vm from 'node:vm'

const source = await readFile(new URL('../src/clientesApi.js', import.meta.url), 'utf8')

async function cargar({ token = 'token-demo', status = 200, data = {}, fallaRed = false } = {}) {
  const llamadas = []
  const context = vm.createContext({
    URLSearchParams,
    localStorage: { getItem: () => token },
    fetch: async (url, opciones) => {
      llamadas.push({ url, opciones })
      if (fallaRed) throw new Error('falló la conexión')
      return { ok: status < 400, status, json: async () => data }
    },
  })
  const module = new vm.SourceTextModule(source, {
    context,
    initializeImportMeta(meta) { meta.env = { VITE_CLIENTES_URL: 'https://clientes.example/' } },
  })
  await module.link(() => {})
  await module.evaluate()
  return { api: module.namespace.clientesApi, llamadas }
}

test('el listado envía el token y conserva el cursor', async () => {
  const { api, llamadas } = await cargar({ data: { clientes: [], siguiente: 'cli_2' } })
  const data = await api.listar('cli_1')
  assert.equal(llamadas[0].url, 'https://clientes.example/clientes?limite=50&siguiente=cli_1')
  assert.equal(llamadas[0].opciones.headers.Authorization, 'Bearer token-demo')
  assert.equal(data.siguiente, 'cli_2')
})

test('crear contacto principal envía un booleano a la ruta del cliente', async () => {
  const { api, llamadas } = await cargar({ data: { contacto_id: 'con_1' } })
  await api.crearContacto('cli_1', { nombre: 'Ana', es_principal: true })
  assert.equal(llamadas[0].url, 'https://clientes.example/clientes/cli_1/contactos')
  assert.equal(llamadas[0].opciones.method, 'POST')
  assert.equal(JSON.parse(llamadas[0].opciones.body).es_principal, true)
})

test('documentos usa rutas protegidas del cliente y envía el archivo codificado', async () => {
  const { api, llamadas } = await cargar({ data: { documento: { documento_id: 'doc_1' } } })
  await api.subirDocumento('cli_1', { nombre: 'contrato.pdf', contenido_base64: 'cGRm' })
  await api.descargarDocumento('cli_1', 'doc_1')
  assert.equal(llamadas[0].url, 'https://clientes.example/clientes/cli_1/documentos')
  assert.equal(JSON.parse(llamadas[0].opciones.body).contenido_base64, 'cGRm')
  assert.equal(llamadas[1].url, 'https://clientes.example/clientes/cli_1/documentos/doc_1/descargar')
  assert.equal(llamadas[1].opciones.headers.Authorization, 'Bearer token-demo')
})

test('sin token o sin conexión se muestran errores y no se simulan datos', async () => {
  const sinToken = await cargar({ token: null })
  await assert.rejects(sinToken.api.listar(), /No se encontró la sesión/)
  assert.equal(sinToken.llamadas.length, 0)
  const sinRed = await cargar({ fallaRed: true })
  await assert.rejects(sinRed.api.listar(), /No se pudo conectar/)
})
