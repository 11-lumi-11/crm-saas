import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import vm from 'node:vm'

const storeSource = await readFile(new URL('../src/store.js', import.meta.url), 'utf8')
const apiSource = await readFile(new URL('../src/authApi.js', import.meta.url), 'utf8')

function almacenamiento(inicial = {}) {
  const datos = new Map(Object.entries(inicial))
  return {
    getItem: k => datos.get(k) ?? null,
    setItem: (k, v) => datos.set(k, String(v)),
    removeItem: k => datos.delete(k),
  }
}

async function cargar({ storage = almacenamiento(), responder } = {}) {
  const llamadas = []
  const context = vm.createContext({
    localStorage: storage,
    URLSearchParams,
    structuredClone,
    setTimeout: () => 1,
    clearTimeout: () => {},
    fetch: async (url, opciones) => {
      llamadas.push({ url, opciones })
      return responder(url, opciones)
    },
  })
  const api = new vm.SourceTextModule(apiSource, {
    context,
    initializeImportMeta(meta) { meta.env = { VITE_USUARIOS_URL: 'https://usuarios.example' } },
  })
  const react = new vm.SyntheticModule(['useSyncExternalStore'], function () {
    this.setExport('useSyncExternalStore', (_, snapshot) => snapshot())
  }, { context })
  const store = new vm.SourceTextModule(storeSource, { context })
  await store.link(specifier => specifier === 'react' ? react : api)
  await store.evaluate()
  return { store: store.namespace, api: api.namespace, storage, llamadas }
}

const respuesta = (data, status = 200) => ({ ok: status < 400, status, json: async () => data })

test('el registro no crea sesión ni reutiliza tokens anteriores', async () => {
  const { store, storage, llamadas } = await cargar({ responder: () => respuesta({ tenant_id: 'ten_1', usuario_id: 'usr_1' }, 201) })
  assert.equal(await store.registro({ empresa: 'Empresa', nombre: 'Admin', correo: 'a@example.test', contrasena: 'secreto', rubro: 'Ventas' }), '')
  assert.equal(store.useCrm().s, null)
  assert.equal(storage.getItem('auth_token'), null)
  assert.equal(llamadas[0].url, 'https://usuarios.example/tenants')
})

test('el login guarda la sesión y permite restaurarla al recargar', async () => {
  const fake = { token: 'token-demo', tenant_id: 'ten_1', usuario_id: 'usr_1', rol: 'admin', expira_en_segundos: 3600 }
  const { store, storage } = await cargar({ responder: () => respuesta(fake) })
  assert.equal(await store.login({ correo: 'a@example.test', contrasena: 'secreto' }), '')
  assert.equal(store.useCrm().s.usuario_id, 'usr_1')
  const recarga = await cargar({ storage, responder: () => respuesta(fake) })
  assert.equal(recarga.store.useCrm().s.tenant_id, 'ten_1')
  recarga.store.salir()
  assert.equal(storage.getItem('auth_token'), null)
  assert.equal(storage.getItem('crm-saas.sesion'), null)
})

test('una sesión vencida no se restaura', async () => {
  const storage = almacenamiento({ auth_token: 'vencido', 'crm-saas.sesion': JSON.stringify({
    s: { usuario_id: 'usr_1', tenant_id: 'ten_1', rol: 'admin' }, expira_en: Date.now() - 1000,
  }) })
  const { store } = await cargar({ storage, responder: () => respuesta({}) })
  assert.equal(store.useCrm().s, null)
  assert.equal(storage.getItem('auth_token'), null)
})

test('una respuesta incompleta y los errores de negocio no inician sesión', async () => {
  const incompleta = await cargar({ responder: () => respuesta({ token: 'token-demo' }) })
  assert.match(await incompleta.store.login({ correo: 'a@example.test' }), /incompleta/)
  assert.equal(incompleta.store.useCrm().s, null)
  const error = await cargar({ responder: () => respuesta({ mensaje: 'Credenciales inválidas' }, 401) })
  assert.equal(await error.store.login({ correo: 'a@example.test' }), 'Credenciales inválidas')
  assert.equal(error.store.useCrm().s, null)
})

test('el listado de usuarios conserva el cursor de la API', async () => {
  const storage = almacenamiento({ auth_token: 'token-demo' })
  const { api, llamadas } = await cargar({ storage, responder: () => respuesta({ usuarios: [{ usuario_id: 'usr_1' }], siguiente: 'usr_1' }) })
  storage.setItem('auth_token', 'token-demo')
  const datos = await api.listarUsuariosApi('usr_anterior')
  const url = new URL(llamadas[0].url)
  assert.equal(url.searchParams.get('siguiente'), 'usr_anterior')
  assert.equal(datos.usuarios[0].usuario_id, 'usr_1')
  assert.equal(datos.siguiente, 'usr_1')
})
