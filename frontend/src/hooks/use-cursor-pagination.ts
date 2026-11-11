import { useCallback, useEffect, useRef, useState } from 'react'
import type { Pagina } from '../types'

export function useCursorPagination<T, F extends object>(cargar: (filtros: F & { siguiente?: string | null }) => Promise<Pagina<T>>, filtros: F) {
  const [items, setItems] = useState<T[]>([]); const [siguiente, setSiguiente] = useState<string | null>(null); const [cargando, setCargando] = useState(true); const [error, setError] = useState<Error | null>(null)
  const filtrosRef = useRef(filtros); const clave = JSON.stringify(filtros)
  const obtener = useCallback(async (cursor: string | null, reemplazar: boolean) => {
    setCargando(true); setError(null)
    try {
      const pagina = await cargar({ ...filtrosRef.current, siguiente: cursor })
      setItems((actual) => reemplazar ? pagina.items : [...actual, ...pagina.items]); setSiguiente(pagina.siguiente)
    } catch (causa) { setError(causa instanceof Error ? causa : new Error('No se pudo cargar la información.')) } finally { setCargando(false) }
  }, [cargar])
  useEffect(() => { filtrosRef.current = filtros; void obtener(null, true) }, [clave, obtener, filtros])
  // Una página filtrada puede quedar vacía y tener cursor: continuamos automáticamente.
  useEffect(() => { if (!cargando && items.length === 0 && siguiente) void obtener(siguiente, false) }, [cargando, items.length, siguiente, obtener])
  return { items, cargando, error, siguiente, recargar: () => obtener(null, true), cargarMas: () => siguiente && obtener(siguiente, false) }
}
