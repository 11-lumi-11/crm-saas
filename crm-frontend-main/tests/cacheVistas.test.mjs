import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import vm from 'node:vm'

async function preparar() {
  let ahora = 1000, indice = 0, efectos = [], llamadas = 0
  const refs = [], dependencias = []
  const context = vm.createContext({ Date: { now: () => ahora } })
  const react = new vm.SyntheticModule(['useEffect', 'useRef'], function () {
    this.setExport('useRef', valor => refs[indice++] ||= { current: valor })
    this.setExport('useEffect', (fn, deps) => {
      const i = indice++
      if (!dependencias[i] || deps.some((d, j) => d !== dependencias[i][j])) efectos.push(fn)
      dependencias[i] = deps
    })
  }, { context })
  const modulo = new vm.SourceTextModule(await readFile(new URL('../src/cacheVistas.js', import.meta.url), 'utf8'), { context })
  await modulo.link(() => react); await modulo.evaluate()
  const render = activa => {
    indice = 0; efectos = []
    const cache = modulo.namespace.useCacheVista('clientes', activa, () => { llamadas++ })
    efectos.forEach(f => f())
    return cache
  }
  return { render, invalidar: modulo.namespace.invalidarVistas, tiempo: n => { ahora += n }, llamadas: () => llamadas }
}

test('al volver usa la caché reciente y refresca si caduca o se invalida', async () => {
  const p = await preparar()
  let cache = p.render(true)
  assert.equal(p.llamadas(), 1)
  cache.registrarCarga(cache.iniciarCarga())
  p.render(false); p.render(true)
  assert.equal(p.llamadas(), 1)
  p.tiempo(60000); p.render(false); cache = p.render(true)
  assert.equal(p.llamadas(), 2)
  cache.registrarCarga(cache.iniciarCarga())
  p.invalidar('clientes'); p.render(false); p.render(true)
  assert.equal(p.llamadas(), 3)
})

test('descarta respuestas antiguas y conserva la invalidación durante una consulta', async () => {
  const p = await preparar(), cache = p.render(true)
  const vieja = cache.iniciarCarga(), nueva = cache.iniciarCarga()
  assert.equal(cache.esActual(vieja), false)
  assert.equal(cache.esActual(nueva), true)
  p.invalidar('clientes'); cache.registrarCarga(nueva)
  p.render(false); p.render(true)
  assert.equal(p.llamadas(), 2)
})

test('precarga una sección una vez incluso si aún no está visible', async () => {
  const p = await preparar()
  const cache = p.render(false)
  assert.equal(p.llamadas(), 1)
  cache.registrarCarga(cache.iniciarCarga())
  p.render(true)
  assert.equal(p.llamadas(), 1)
})
