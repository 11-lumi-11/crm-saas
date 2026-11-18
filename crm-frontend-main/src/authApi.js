// Solo se publica la URL de la API; el secreto JWT permanece en el backend.
const usuariosUrl = (import.meta.env.VITE_USUARIOS_URL || 'https://6ge9waha1h.execute-api.us-east-1.amazonaws.com').replace(/\/$/, '')
export const AUTH_ENDPOINTS = {
  login: `${usuariosUrl}/usuarios/login`,
  registro: `${usuariosUrl}/tenants`,
  crearUsuario: `${usuariosUrl}/usuarios`,
}

async function request(endpoint, payload, headers = {}) {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...headers },
    body: JSON.stringify(payload),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.mensaje || data.message || data.error || `Solicitud fallida (${response.status}).`)
  return data
}

export const iniciarSesionApi = (datos) => request(AUTH_ENDPOINTS.login, datos)
export const registrarApi = ({ empresa, nombre, correo, contrasena, rubro }) => request(AUTH_ENDPOINTS.registro, {
  nombre_empresa: empresa,
  nombre_admin: nombre,
  correo,
  contrasena,
  rubro,
})

export const crearUsuarioApi = (datos) => {
  const token = localStorage.getItem('auth_token')
  if (!token) return Promise.reject(new Error('No se encontró el token de sesión. Vuelve a iniciar sesión.'))
  return request(AUTH_ENDPOINTS.crearUsuario, datos, { Authorization: token })
}

export const listarUsuariosApi = async (siguiente) => {
  const token = localStorage.getItem('auth_token')
  if (!token) throw new Error('No se encontró el token de sesión. Vuelve a iniciar sesión.')
  const params = new URLSearchParams({ limite: '50', ...(siguiente ? { siguiente } : {}) })
  const response = await fetch(`${AUTH_ENDPOINTS.crearUsuario}?${params}`, {
    method: 'GET',
    headers: { Accept: 'application/json', Authorization: token },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.mensaje || data.message || data.error || `Solicitud fallida (${response.status}).`)
  let body = data.body ?? data.data ?? data
  if (typeof body === 'string') {
    try { body = JSON.parse(body) } catch { /* deja que la validación de abajo muestre un error claro */ }
  }
  const usuarios = Array.isArray(body) ? body : body.usuarios || body.items || body.data || []
  if (!Array.isArray(usuarios)) throw new Error('La respuesta de usuarios no tiene el formato esperado.')
  return { usuarios, siguiente: body.siguiente || null }
}

export const modificarUsuarioApi = (usuarioId, cambios) => {
  const token = localStorage.getItem('auth_token')
  if (!token) return Promise.reject(new Error('No se encontró el token de sesión. Vuelve a iniciar sesión.'))
  return fetch(`${AUTH_ENDPOINTS.crearUsuario}/${encodeURIComponent(usuarioId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json', Authorization: token },
    body: JSON.stringify(cambios),
  }).then(async (response) => {
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.mensaje || data.message || data.error || `Solicitud fallida (${response.status}).`)
    return data
  })
}
