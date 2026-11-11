import { request } from './http'
import type { Cliente, Contacto, Pagina } from '../types'

const base = import.meta.env.VITE_CLIENTES_URL as string | undefined ?? ''
export type ClientePayload = Pick<Cliente, 'nombre' | 'tipo' | 'documento' | 'correo' | 'telefono' | 'industria' | 'ciudad' | 'estado'> & { responsable_id?: string }
export const clientesApi = {
  listar: async (opciones: { siguiente?: string | null; responsable_id?: string; limite?: number } = {}): Promise<Pagina<Cliente>> => {
    const params = new URLSearchParams({ limite: String(opciones.limite ?? 30) })
    if (opciones.siguiente) params.set('siguiente', opciones.siguiente)
    if (opciones.responsable_id) params.set('responsable_id', opciones.responsable_id)
    const data = await request<{ clientes: Cliente[]; siguiente: string | null }>(base, `/clientes?${params}`)
    return { items: data.clientes, siguiente: data.siguiente }
  },
  obtener: async (id: string) => (await request<{ cliente: Cliente }>(base, `/clientes/${id}`)).cliente,
  crear: async (datos: ClientePayload) => request<{ cliente_id: string }>(base, '/clientes', { method: 'POST', body: JSON.stringify(datos) }),
  actualizar: async (id: string, datos: Partial<ClientePayload>) => (await request<{ cliente: Cliente }>(base, `/clientes/${id}`, { method: 'PUT', body: JSON.stringify(datos) })).cliente,
  eliminar: (id: string) => request<void>(base, `/clientes/${id}`, { method: 'DELETE' }),
  listarContactos: async (clienteId: string, siguiente?: string | null): Promise<Pagina<Contacto>> => {
    const params = new URLSearchParams({ limite: '50' }); if (siguiente) params.set('siguiente', siguiente)
    const data = await request<{ contactos: Contacto[]; siguiente: string | null }>(base, `/clientes/${clienteId}/contactos?${params}`)
    return { items: data.contactos, siguiente: data.siguiente }
  },
  crearContacto: (clienteId: string, datos: Omit<Contacto, 'contacto_id' | 'cliente_id' | 'fecha_creacion'>) => request<{ contacto_id: string }>(base, `/clientes/${clienteId}/contactos`, { method: 'POST', body: JSON.stringify(datos) }),
}
