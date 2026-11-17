const base = (import.meta.env.VITE_NOTIFICACIONES_URL || 'https://wjh7j70pil.execute-api.us-east-1.amazonaws.com').replace(/\/$/, '')

async function request(path, opciones = {}) {
  const token = localStorage.getItem('auth_token')
  if (!token) throw new Error('No se encontró la sesión. Vuelve a iniciar sesión.')
  let respuesta
  try {
    respuesta = await fetch(`${base}${path}`, {
      ...opciones,
      headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
    })
  } catch {
    throw new Error('No se pudo conectar con Notificaciones. Comprueba tu conexión e inténtalo de nuevo.')
  }
  const datos = await respuesta.json().catch(() => ({}))
  if (!respuesta.ok) throw new Error(datos.mensaje || `No se pudo completar la solicitud (${respuesta.status}).`)
  return datos
}

export const notificacionesApi = {
  listar: ({ siguiente, soloNoLeidas = false } = {}) => {
    const params = new URLSearchParams({ limite: '50' })
    if (siguiente) params.set('siguiente', siguiente)
    if (soloNoLeidas) params.set('solo_no_leidas', 'true')
    return request(`/notificaciones?${params}`)
  },
  marcarLeida: notificacionId => request(`/notificaciones/${encodeURIComponent(notificacionId)}/leer`, { method: 'PUT' }),
}
