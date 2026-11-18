const CLAVE = 'crm-saas.vista'
const VISTAS = ['inicio', 'clientes', 'oportunidades', 'actividades', 'productos', 'cotizaciones', 'notificaciones', 'usuarios']

export function leerVista(sesion) {
  const inicio = { vista: 'inicio', tab: 0 }
  if (!sesion) return inicio
  try {
    const dato = JSON.parse(sessionStorage.getItem(CLAVE) || 'null')
    if (!dato || dato.tenant_id !== sesion.tenant_id || dato.usuario_id !== sesion.usuario_id ||
        !VISTAS.includes(dato.vista) || (dato.vista === 'usuarios' && sesion.rol !== 'admin')) return inicio
    return { vista: dato.vista, tab: dato.vista === 'inicio' && dato.tab === 1 ? 1 : 0 }
  } catch { return inicio }
}

export function guardarVista(sesion, vista, tab = 0) {
  try { sessionStorage.setItem(CLAVE, JSON.stringify({ tenant_id: sesion.tenant_id, usuario_id: sesion.usuario_id, vista, tab })) }
  catch { /* La navegación sigue funcionando si el navegador bloquea el almacenamiento. */ }
}

export function limpiarVista() {
  try { sessionStorage.removeItem(CLAVE) } catch { /* No hay datos de navegación disponibles. */ }
}
