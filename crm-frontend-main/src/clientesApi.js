// URL pública de API Gateway; la identidad se obtiene del token de sesión.
const base = (import.meta.env.VITE_CLIENTES_URL || 'https://3l552xeuv9.execute-api.us-east-1.amazonaws.com').replace(/\/$/, '')

async function request(path, opciones = {}) {
  const token = localStorage.getItem('auth_token')
  if (!token) throw new Error('No se encontró la sesión. Vuelve a iniciar sesión.')
  let response
  try {
    response = await fetch(`${base}${path}`, {
      ...opciones,
      headers: { Accept: 'application/json', Authorization: `Bearer ${token}`,
        ...(opciones.body ? { 'Content-Type': 'application/json' } : {}) },
    })
  } catch {
    throw new Error('No se pudo conectar con Clientes. Comprueba tu conexión e inténtalo de nuevo.')
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.mensaje || `No se pudo completar la solicitud (${response.status}).`)
  return data
}

function listado(path, siguiente) {
  const parametros = new URLSearchParams({ limite: '50' })
  if (siguiente) parametros.set('siguiente', siguiente)
  return request(`${path}?${parametros}`)
}

export const clientesApi = {
  listar: siguiente => listado('/clientes', siguiente),
  obtener: id => request(`/clientes/${encodeURIComponent(id)}`),
  crear: datos => request('/clientes', { method: 'POST', body: JSON.stringify(datos) }),
  actualizar: (id, datos) => request(`/clientes/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(datos) }),
  contactos: (id, siguiente) => listado(`/clientes/${encodeURIComponent(id)}/contactos`, siguiente),
  crearContacto: (id, datos) => request(`/clientes/${encodeURIComponent(id)}/contactos`, { method: 'POST', body: JSON.stringify(datos) }),
}
