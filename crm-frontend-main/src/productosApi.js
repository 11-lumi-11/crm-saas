const base = (import.meta.env.VITE_PRODUCTOS_URL || 'https://so7sgzu6y6.execute-api.us-east-1.amazonaws.com').replace(/\/$/, '')

async function request(path, opciones = {}) {
  const token = localStorage.getItem('auth_token')
  if (!token) throw new Error('No se encontró la sesión. Vuelve a iniciar sesión.')
  let respuesta
  try {
    respuesta = await fetch(`${base}${path}`, {
      ...opciones,
      headers: { Accept: 'application/json', Authorization: `Bearer ${token}`,
        ...(opciones.body ? { 'Content-Type': 'application/json' } : {}) },
    })
  } catch {
    throw new Error('No se pudo conectar con Productos y Cotizaciones. Comprueba tu conexión e inténtalo de nuevo.')
  }
  const datos = await respuesta.json().catch(() => ({}))
  if (!respuesta.ok) throw new Error(datos.mensaje || `No se pudo completar la solicitud (${respuesta.status}).`)
  return datos
}

const id = valor => encodeURIComponent(valor)
const cuerpo = (method, datos) => ({ method, body: JSON.stringify(datos) })
const listado = (ruta, siguiente) => request(`${ruta}?${new URLSearchParams({ limite: '50', ...(siguiente ? { siguiente } : {}) })}`)

export const productosApi = {
  listar: siguiente => listado('/productos', siguiente),
  crear: datos => request('/productos', cuerpo('POST', datos)),
  actualizar: (valor, datos) => request(`/productos/${id(valor)}`, cuerpo('PUT', datos)),
}

export const cotizacionesApi = {
  listar: siguiente => listado('/cotizaciones', siguiente),
  obtener: valor => request(`/cotizaciones/${id(valor)}`),
  crear: datos => request('/cotizaciones', cuerpo('POST', datos)),
  enviar: valor => request(`/cotizaciones/${id(valor)}/enviar`, { method: 'PUT' }),
  aceptar: valor => request(`/cotizaciones/${id(valor)}/aceptar`, { method: 'PUT' }),
  rechazar: (valor, datos = {}) => request(`/cotizaciones/${id(valor)}/rechazar`, cuerpo('PUT', datos)),
  archivar: valor => request(`/cotizaciones/${id(valor)}`, { method: 'DELETE' }),
}
