const urls = {
  oportunidades: (import.meta.env.VITE_OPORTUNIDADES_URL || 'https://xka1oaqzad.execute-api.us-east-1.amazonaws.com').replace(/\/$/, ''),
  actividades: (import.meta.env.VITE_ACTIVIDADES_URL || 'https://47idshdw10.execute-api.us-east-1.amazonaws.com').replace(/\/$/, ''),
}

async function request(servicio, path, opciones = {}) {
  const token = localStorage.getItem('auth_token')
  if (!token) throw new Error('No se encontró la sesión. Vuelve a iniciar sesión.')
  let respuesta
  try {
    respuesta = await fetch(`${urls[servicio]}${path}`, {
      ...opciones,
      headers: { Accept: 'application/json', Authorization: `Bearer ${token}`,
        ...(opciones.body ? { 'Content-Type': 'application/json' } : {}) },
    })
  } catch {
    throw new Error(`No se pudo conectar con ${servicio}. Comprueba tu conexión e inténtalo de nuevo.`)
  }
  const datos = await respuesta.json().catch(() => ({}))
  if (!respuesta.ok) throw new Error(datos.mensaje || `No se pudo completar la solicitud (${respuesta.status}).`)
  return datos
}

const id = valor => encodeURIComponent(valor)
const opciones = (metodo, datos) => ({ method: metodo, body: JSON.stringify(datos) })

export const oportunidadesApi = {
  listar: siguiente => request('oportunidades', `/oportunidades?${new URLSearchParams({ limite: '50', ...(siguiente ? { siguiente } : {}) })}`),
  crear: datos => request('oportunidades', '/oportunidades', opciones('POST', datos)),
  obtener: valor => request('oportunidades', `/oportunidades/${id(valor)}`),
  historial: valor => request('oportunidades', `/oportunidades/${id(valor)}/historial`),
  etapa: (valor, datos) => request('oportunidades', `/oportunidades/${id(valor)}/etapa`, opciones('PUT', datos)),
}

export const actividadesApi = {
  listar: ({ siguiente, responsable_id } = {}) => request('actividades', `/actividades?${new URLSearchParams({ limite: '50', ...(siguiente ? { siguiente } : {}), ...(responsable_id ? { responsable_id } : {}) })}`),
  completar: valor => request('actividades', `/actividades/${id(valor)}/completar`, { method: 'PUT' }),
}
