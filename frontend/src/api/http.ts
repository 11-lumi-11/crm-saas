import { limpiarSesion, obtenerSesion } from '../lib/session'
import { clientesMock, contactosMock, oportunidadesMock } from '../mocks'

export class ApiError extends Error { constructor(public status: number, public codigo: string, mensaje: string) { super(mensaje) } }

export async function request<T>(base: string, ruta: string, opciones: RequestInit = {}): Promise<T> {
  if (import.meta.env.DEV && obtenerSesion()?.token === 'demo-local') {
    if (opciones.method && opciones.method !== 'GET') throw new ApiError(400, 'demo_solo_lectura', 'La demostración es de solo lectura.')
    const path = ruta.split('?')[0]
    if (path === '/clientes') return { clientes: clientesMock, siguiente: null } as T
    if (path === '/oportunidades') return { oportunidades: oportunidadesMock, siguiente: null } as T
    const contactos = path.match(/^\/clientes\/([^/]+)\/contactos$/)
    if (contactos) return { contactos: contactosMock.filter(c => c.cliente_id === contactos[1]), siguiente: null } as T
    const cliente = path.match(/^\/clientes\/([^/]+)$/)
    if (cliente) return { cliente: clientesMock.find(c => c.cliente_id === cliente[1]) } as T
    throw new ApiError(404, 'no_disponible', 'No disponible en la demostración.')
  }
  if (!base) throw new ApiError(503, 'servicio_no_configurado', 'Este servicio todavía no está configurado.')
  const sesion = obtenerSesion()
  const response = await fetch(`${base.replace(/\/$/, '')}${ruta}`, {
    ...opciones,
    headers: { 'Content-Type': 'application/json', ...(sesion?.token ? { Authorization: `Bearer ${sesion.token}` } : {}), ...opciones.headers },
  })
  const cuerpo = await response.json().catch(() => ({})) as Record<string, unknown>
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      limpiarSesion()
      window.dispatchEvent(new Event('crm:sesion-invalida'))
    }
    throw new ApiError(response.status, String(cuerpo.codigo ?? 'error_api'), String(cuerpo.mensaje ?? 'No se pudo completar la solicitud.'))
  }
  return cuerpo as T
}
