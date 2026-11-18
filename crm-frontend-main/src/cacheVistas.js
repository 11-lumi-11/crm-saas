import { useEffect, useRef } from 'react'

// La caché vive en los componentes montados y se descarta al cerrar sesión o recargar.
const revisiones = new Map()
export const invalidarVistas = (...vistas) => {
  for (const vista of vistas) revisiones.set(vista, (revisiones.get(vista) || 0) + 1)
}
export function useCacheVista(nombre, activa, cargar) {
  const estado = useRef({ cargada: false, fecha: 0, revision: -1 })
  const secuencia = useRef(0)
  const primeraVisita = useRef(true)
  const precargaEnCurso = useRef(false)
  const cargarRef = useRef(cargar)
  cargarRef.current = cargar
  useEffect(() => {
    const primera = primeraVisita.current
    primeraVisita.current = false
    if ((!activa && !primera) || precargaEnCurso.current) return
    const actual = estado.current
    if (!actual.cargada || actual.revision !== (revisiones.get(nombre) || 0) || Date.now() - actual.fecha >= 60000) {
      const solicitud = cargarRef.current()
      if (solicitud && typeof solicitud.finally === 'function') {
        precargaEnCurso.current = true
        solicitud.finally(() => { precargaEnCurso.current = false })
      }
    }
  }, [activa, nombre])
  return {
    estado,
    iniciarCarga: () => ({ secuencia: ++secuencia.current, revision: revisiones.get(nombre) || 0 }),
    esActual: carga => carga.secuencia === secuencia.current,
    registrarCarga: carga => {
      estado.current = { cargada: true, fecha: Date.now(), revision: carga.revision }
    },
  }
}
