import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import vm from 'node:vm'
const source = await readFile(new URL('../src/navegacion.js', import.meta.url), 'utf8')
async function preparar() {
  const datos = new Map()
  const context = vm.createContext({ sessionStorage: { getItem: k => datos.get(k), setItem: (k, v) => datos.set(k, v), removeItem: k => datos.delete(k) } })
  const modulo = new vm.SourceTextModule(source, { context }); await modulo.link(() => {}); await modulo.evaluate()
  return modulo.namespace
}
const admin = { usuario_id: 'usr_1', tenant_id: 'ten_1', rol: 'admin' }
test('recupera la vista y pestaña para la misma cuenta', async () => {
  const n = await preparar(); n.guardarVista(admin, 'inicio', 1)
  assert.equal(n.leerVista(admin).vista, 'inicio'); assert.equal(n.leerVista(admin).tab, 1)
  n.guardarVista(admin, 'cotizaciones'); assert.equal(n.leerVista(admin).vista, 'cotizaciones')
  n.limpiarVista(); assert.equal(n.leerVista(admin).vista, 'inicio')
})
test('no restaura vistas de otra identidad ni administración sin permisos', async () => {
  const n = await preparar(); n.guardarVista(admin, 'usuarios')
  assert.equal(n.leerVista({ ...admin, usuario_id: 'usr_2' }).vista, 'inicio')
  assert.equal(n.leerVista({ ...admin, tenant_id: 'ten_2' }).vista, 'inicio')
  assert.equal(n.leerVista({ ...admin, rol: 'vendedor' }).vista, 'inicio')
})
