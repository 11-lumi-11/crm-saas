import type { Sesion } from '../types'

const CLAVE = 'crm-saas.sesion'
export const obtenerSesion = (): Sesion | null => { try { const valor = localStorage.getItem(CLAVE); return valor ? JSON.parse(valor) as Sesion : null } catch { return null } }
export const guardarSesion = (sesion: Sesion) => localStorage.setItem(CLAVE, JSON.stringify(sesion))
export const limpiarSesion = () => localStorage.removeItem(CLAVE)
