import type { Notificacion, Pagina } from '../types'
import { notificacionesMock } from '../mocks'
import { request } from './http'
const base = import.meta.env.VITE_NOTIFICACIONES_URL as string | undefined ?? ''
export const notificacionesApi = { listar: async (): Promise<Pagina<Notificacion>> => base ? request<{ notificaciones: Notificacion[]; siguiente: string | null }>(base, '/notificaciones').then((d) => ({ items: d.notificaciones, siguiente: d.siguiente })) : { items: notificacionesMock, siguiente: null } }
