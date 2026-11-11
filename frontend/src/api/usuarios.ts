import { request } from './http'
import type { Pagina, Usuario } from '../types'

const base = import.meta.env.VITE_USUARIOS_URL as string | undefined ?? ''
export interface LoginRespuesta { token: string; usuario_id: string; tenant_id: string; rol: 'admin' | 'gerente' | 'vendedor'; expira_en_segundos: number }
export const usuariosApi = {
  login: (correo: string, contrasena: string) => request<LoginRespuesta>(base, '/usuarios/login', { method: 'POST', body: JSON.stringify({ correo, contrasena }) }),
  registrarTenant: (datos: { nombre_empresa: string; rubro: string; nombre_admin: string; correo: string; contrasena: string }) => request<{ tenant_id: string; usuario_id: string }>(base, '/tenants', { method: 'POST', body: JSON.stringify(datos) }),
  listar: async (siguiente?: string | null, limite = 100): Promise<Pagina<Usuario>> => {
    const query = new URLSearchParams({ limite: String(limite) }); if (siguiente) query.set('siguiente', siguiente)
    const data = await request<{ usuarios: Usuario[]; siguiente: string | null }>(base, `/usuarios?${query}`)
    return { items: data.usuarios, siguiente: data.siguiente }
  },
}
