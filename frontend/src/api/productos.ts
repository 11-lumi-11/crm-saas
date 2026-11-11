import { request } from './http'
const base = import.meta.env.VITE_PRODUCTOS_URL as string | undefined ?? ''
export const productosApi = { listar: () => base ? request(base, '/productos') : Promise.resolve({ productos: [], siguiente: null }) }
