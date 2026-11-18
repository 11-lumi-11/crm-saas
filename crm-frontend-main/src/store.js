import { useSyncExternalStore } from 'react'
import { iniciarSesionApi, registrarApi } from './authApi'

/* ============ Utilidades (nombres según Documento Base) ============ */
export const ETAPAS = ['nueva', 'en_negociacion', 'ganada', 'perdida']
export const txt = (s) => (s || '').replaceAll('_', ' ')
export const ahora = () => new Date().toISOString()
export const dia = (f) => (f ? f.slice(0, 10) : '—')
export const soles = (n, m = 'PEN') => `${m === 'PEN' ? 'S/' : m} ${Number(n).toLocaleString('es-PE')}`
const CLAVE_SESION = 'crm-saas.sesion'
const leerSesion = () => {
  try {
    const guardada = JSON.parse(localStorage.getItem(CLAVE_SESION) || 'null')
    if (!guardada || !localStorage.getItem('auth_token') || !guardada.s?.usuario_id || !guardada.s?.tenant_id ||
        !['admin', 'gerente', 'vendedor'].includes(guardada.s.rol) || !Number.isFinite(guardada.expira_en) || guardada.expira_en <= Date.now()) {
      localStorage.removeItem(CLAVE_SESION)
      localStorage.removeItem('auth_token')
      return null
    }
    return guardada
  } catch {
    localStorage.removeItem(CLAVE_SESION)
    localStorage.removeItem('auth_token')
    return null
  }
}
const sesionGuardada = leerSesion()
let state = { s: sesionGuardada?.s || null, tenant: sesionGuardada ? { nombre: sesionGuardada.tenantNombre || 'Mi empresa' } : null, aviso: '', q: '' }
const subs = new Set()
const subscribe = (f) => { subs.add(f); return () => subs.delete(f) }
const set = (p) => { state = { ...state, ...(typeof p === 'function' ? p(state) : p) }; subs.forEach((f) => f()) }

/* --- auth (el token JWT real traería usuario_id, tenant_id y rol) --- */
const sesionDesdeRespuesta = (respuesta, datos) => {
  let contenido = respuesta.body || respuesta.data?.body || respuesta
  if (typeof contenido === 'string') {
    try { contenido = JSON.parse(contenido) } catch { contenido = respuesta }
  }
  const usuario = contenido.usuario || contenido.user || contenido.data?.usuario || contenido.data?.user || contenido.data || contenido
  const tenant_id = usuario.tenant_id
  const usuario_id = usuario.usuario_id
  const nombre = usuario.nombre || usuario.name || datos.nombre || datos.correo
  const rol = usuario.rol
  const tenantNombre = usuario.empresa || usuario.tenant?.nombre || usuario.tenant?.name || datos.empresa || 'Mi empresa'
  const token = contenido.token || contenido.access_token || contenido.data?.token || contenido.data?.access_token || respuesta.token || respuesta.access_token
  const duracion = Number(contenido.expira_en_segundos)
  if (!token || !tenant_id || !usuario_id || !['admin', 'gerente', 'vendedor'].includes(rol) || !Number.isFinite(duracion) || duracion <= 0) {
    throw new Error('La respuesta de inicio de sesión está incompleta. Inténtalo nuevamente.')
  }
  const s = { usuario_id, tenant_id, rol, nombre }
  const expira_en = Date.now() + duracion * 1000
  localStorage.setItem('auth_token', token)
  localStorage.setItem(CLAVE_SESION, JSON.stringify({ s, tenantNombre, expira_en }))
  programarCaducidad(expira_en)
  set({ s, tenant: { nombre: tenantNombre } })
}
export const login = async (datos) => {
  try { sesionDesdeRespuesta(await iniciarSesionApi(datos), datos); return '' }
  catch (error) { return error.message || 'No se pudo iniciar sesión.' }
}
export const registro = async (datos) => {
  try { await registrarApi(datos); return '' }
  catch (error) { return error.message || 'No se pudo completar el registro.' }
}
let temporizadorSesion
function programarCaducidad(expiraEn) {
  clearTimeout(temporizadorSesion)
  temporizadorSesion = setTimeout(() => salir(), Math.max(0, expiraEn - Date.now()))
}
export const salir = () => {
  clearTimeout(temporizadorSesion)
  localStorage.removeItem('auth_token')
  localStorage.removeItem(CLAVE_SESION)
  set({ s: null, tenant: null, q: '' })
}
if (sesionGuardada) programarCaducidad(sesionGuardada.expira_en)
export const setQ = (q) => set({ q })

/* Estado de sesión; los datos comerciales se consultan en sus API. */
const subir = () => state
export const useCrm = () => {
  const st = useSyncExternalStore(subscribe, subir)
  return { ...st, esVend: st.s?.rol === 'vendedor', esAdmin: st.s?.rol === 'admin' }
}
