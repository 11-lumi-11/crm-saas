import type { Actividad, Pagina } from '../types'
import { actividadesMock } from '../mocks'
import { request } from './http'
const base = import.meta.env.VITE_ACTIVIDADES_URL as string | undefined ?? ''
export const actividadesApi = { listar: async (): Promise<Pagina<Actividad>> => base ? request<{ actividades: Actividad[]; siguiente: string | null }>(base, '/actividades').then((d) => ({ items: d.actividades, siguiente: d.siguiente })) : { items: actividadesMock, siguiente: null } }
