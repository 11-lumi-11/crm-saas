import { request } from './http'
import type { Oportunidad, Pagina } from '../types'

const base = import.meta.env.VITE_OPORTUNIDADES_URL as string | undefined ?? ''
export const oportunidadesApi = {
  listar: async (filtro: { cliente_id?: string; responsable_id?: string; etapa?: string; siguiente?: string | null } = {}): Promise<Pagina<Oportunidad>> => {
    const params = new URLSearchParams({ limite: '50' })
    Object.entries(filtro).forEach(([clave, valor]) => { if (valor) params.set(clave, valor) })
    const data = await request<{ oportunidades: Oportunidad[]; siguiente: string | null }>(base, `/oportunidades?${params}`)
    return { items: data.oportunidades, siguiente: data.siguiente }
  },
}
