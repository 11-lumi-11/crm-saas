import { useSyncExternalStore } from 'react'
import { iniciarSesionApi, registrarApi } from './authApi'

/* ============ Utilidades (nombres según Documento Base) ============ */
export const ETAPAS = ['nueva', 'en_negociacion', 'ganada', 'perdida']
export const txt = (s) => (s || '').replaceAll('_', ' ')
export const ahora = () => new Date().toISOString()
export const dia = (f) => (f ? f.slice(0, 10) : '—')
export const soles = (n, m = 'PEN') => `${m === 'PEN' ? 'S/' : m} ${Number(n).toLocaleString('es-PE')}`
let seq = 1000
export const nid = (p) => `${p}_${String(++seq).padStart(6, '0')}`

/* ============ Datos simulados: reemplazar por fetch() a API Gateway ============
   Ej.: fetch(`${import.meta.env.VITE_API_URL}/clientes`, { headers: { Authorization: token } }) */
const b = (t) => ({ tenant_id: t, fecha_creacion: '2026-11-01T10:00:00Z' })
const SEMILLA = {
  tenants: [
    { tenant_id: 'ten_seguros', nombre: 'Seguros Andinos', rubro: 'Seguros', estado: 'activo' },
    { tenant_id: 'ten_electro', nombre: 'ElectroHogar', rubro: 'Venta de electrodomésticos', estado: 'activo' },
  ],
  usuarios: [
    { ...b('ten_seguros'), usuario_id: 'usr_000001', nombre: 'Lucía Paredes', correo: 'admin@seguros.pe', contrasena_hash: 'demo123', rol: 'admin', estado: 'activo' },
    { ...b('ten_seguros'), usuario_id: 'usr_000002', nombre: 'Marta Quispe', correo: 'marta@seguros.pe', contrasena_hash: 'demo123', rol: 'vendedor', estado: 'activo' },
    { ...b('ten_seguros'), usuario_id: 'usr_000003', nombre: 'Rodrigo Salas', correo: 'gerente@seguros.pe', contrasena_hash: 'demo123', rol: 'gerente', estado: 'activo' },
    { ...b('ten_electro'), usuario_id: 'usr_000004', nombre: 'Camila Rojas', correo: 'admin@electro.pe', contrasena_hash: 'demo123', rol: 'admin', estado: 'activo' },
  ],
  clientes: [
    { ...b('ten_seguros'), cliente_id: 'cli_000001', nombre: 'Constructora Andes', tipo: 'empresa', documento: '20512345678', correo: 'info@andes.pe', telefono: '987654321', industria: 'Construcción', ciudad: 'Lima', estado: 'activo', responsable_id: 'usr_000002' },
    { ...b('ten_seguros'), cliente_id: 'cli_000002', nombre: 'Transportes Rímac', tipo: 'empresa', documento: '20456789123', correo: 'ventas@rimac.pe', telefono: '912345678', industria: 'Transporte', ciudad: 'Arequipa', estado: 'prospecto', responsable_id: 'usr_000002' },
    { ...b('ten_electro'), cliente_id: 'cli_000003', nombre: 'Hotel Miraflores', tipo: 'empresa', documento: '20111222333', correo: 'compras@hotelmira.pe', telefono: '999888777', industria: 'Hotelería', ciudad: 'Lima', estado: 'activo', responsable_id: 'usr_000004' },
  ],
  contactos: [{ ...b('ten_seguros'), contacto_id: 'con_000001', cliente_id: 'cli_000001', nombre: 'Ana Torres', cargo: 'Gerente de compras', correo: 'ana@andes.pe', telefono: '987000111', es_principal: true }],
  oportunidades: [
    { ...b('ten_seguros'), oportunidad_id: 'opo_000001', cliente_id: 'cli_000001', titulo: 'Seguro de flota', monto_estimado: 80000, moneda: 'PEN', etapa: 'en_negociacion', fecha_cierre_estimada: '2026-12-15T00:00:00Z', responsable_id: 'usr_000002' },
    { ...b('ten_seguros'), oportunidad_id: 'opo_000002', cliente_id: 'cli_000002', titulo: 'Seguro vehicular básico', monto_estimado: 24000, moneda: 'PEN', etapa: 'nueva', fecha_cierre_estimada: '2027-01-20T00:00:00Z', responsable_id: 'usr_000002' },
  ],
  historial: [],
  actividades: [{ ...b('ten_seguros'), actividad_id: 'act_000001', tipo: 'llamada', titulo: 'Llamar a Ana por la propuesta', descripcion: '', cliente_id: 'cli_000001', oportunidad_id: 'opo_000001', responsable_id: 'usr_000002', fecha_programada: '2026-11-14T15:00:00Z', estado: 'pendiente', origen: 'manual' }],
  productos: [
    { ...b('ten_seguros'), producto_id: 'pro_000001', nombre: 'Seguro vehicular básico', descripcion: 'Cobertura contra terceros', categoria: 'Vehicular', precio: 2400, moneda: 'PEN', estado: 'activo' },
    { ...b('ten_seguros'), producto_id: 'pro_000002', nombre: 'Seguro de flota premium', descripcion: 'Cobertura total para flotas', categoria: 'Vehicular', precio: 7800, moneda: 'PEN', estado: 'activo' },
  ],
  cotizaciones: [],
  notificaciones: [{ ...b('ten_seguros'), notificacion_id: 'not_000001', usuario_destino_id: 'usr_000002', rol_destino: null, tipo: 'usuario.creado', titulo: '¡Bienvenida, Marta!', mensaje: 'Tu cuenta en Seguros Andinos está lista.', leida: false }],
}

/* ============ Store mínimo (sin librerías) ============ */
const CLAVE_SESION = 'crm-saas.sesion'
const leerSesion = () => {
  try {
    const guardada = JSON.parse(localStorage.getItem(CLAVE_SESION) || 'null')
    if (!guardada || !localStorage.getItem('auth_token') || !guardada.s?.usuario_id || !guardada.s?.tenant_id ||
        !['admin', 'gerente', 'vendedor'].includes(guardada.s.rol) || !Number.isFinite(guardada.expira_en) || guardada.expira_en <= Date.now()) {
      localStorage.removeItem(CLAVE_SESION)
      localStorage.removeItem('auth_token')
      return null
    }
    return guardada
  } catch {
    localStorage.removeItem(CLAVE_SESION)
    localStorage.removeItem('auth_token')
    return null
  }
}
const sesionGuardada = leerSesion()
const dbInicial = sesionGuardada && !SEMILLA.tenants.some(t => t.tenant_id === sesionGuardada.s.tenant_id)
  ? { ...SEMILLA, tenants: [...SEMILLA.tenants, { tenant_id: sesionGuardada.s.tenant_id, nombre: sesionGuardada.tenantNombre, estado: 'activo' }] }
  : SEMILLA
let state = { db: dbInicial, s: sesionGuardada?.s || null, aviso: '', q: '' }
const subs = new Set()
const subscribe = (f) => { subs.add(f); return () => subs.delete(f) }
const set = (p) => { state = { ...state, ...(typeof p === 'function' ? p(state) : p) }; subs.forEach((f) => f()) }
let timer
const decir = (m) => { set({ aviso: m }); clearTimeout(timer); timer = setTimeout(() => set({ aviso: '' }), 2600) }
const M = (fn, msg) => { set((st) => { const n = structuredClone(st.db); fn(n); return { db: n } }); if (msg) decir(msg) }

/* --- auth (el token JWT real traería usuario_id, tenant_id y rol) --- */
const sesionDesdeRespuesta = (respuesta, datos) => {
  let contenido = respuesta.body || respuesta.data?.body || respuesta
  if (typeof contenido === 'string') {
    try { contenido = JSON.parse(contenido) } catch { contenido = respuesta }
  }
  const usuario = contenido.usuario || contenido.user || contenido.data?.usuario || contenido.data?.user || contenido.data || contenido
  const tenant_id = usuario.tenant_id
  const usuario_id = usuario.usuario_id
  const nombre = usuario.nombre || usuario.name || datos.nombre || datos.correo
  const rol = usuario.rol
  const tenantNombre = usuario.empresa || usuario.tenant?.nombre || usuario.tenant?.name || datos.empresa || 'Mi empresa'
  const token = contenido.token || contenido.access_token || contenido.data?.token || contenido.data?.access_token || respuesta.token || respuesta.access_token
  const duracion = Number(contenido.expira_en_segundos)
  if (!token || !tenant_id || !usuario_id || !['admin', 'gerente', 'vendedor'].includes(rol) || !Number.isFinite(duracion) || duracion <= 0) {
    throw new Error('La respuesta de inicio de sesión está incompleta. Inténtalo nuevamente.')
  }
  const s = { usuario_id, tenant_id, rol, nombre }
  const expira_en = Date.now() + duracion * 1000
  localStorage.setItem('auth_token', token)
  localStorage.setItem(CLAVE_SESION, JSON.stringify({ s, tenantNombre, expira_en }))
  programarCaducidad(expira_en)
  set((st) => ({
    s,
    db: { ...st.db, tenants: st.db.tenants.some((t) => t.tenant_id === tenant_id) ? st.db.tenants : [...st.db.tenants, { tenant_id, nombre: tenantNombre, rubro: usuario.rubro || '', estado: 'activo' }] },
  }))
}
export const login = async (datos) => {
  try { sesionDesdeRespuesta(await iniciarSesionApi(datos), datos); return '' }
  catch (error) { return error.message || 'No se pudo iniciar sesión.' }
}
export const registro = async (datos) => {
  try { await registrarApi(datos); return '' }
  catch (error) { return error.message || 'No se pudo completar el registro.' }
}
let temporizadorSesion
function programarCaducidad(expiraEn) {
  clearTimeout(temporizadorSesion)
  temporizadorSesion = setTimeout(() => salir(), Math.max(0, expiraEn - Date.now()))
}
export const salir = () => {
  clearTimeout(temporizadorSesion)
  localStorage.removeItem('auth_token')
  localStorage.removeItem(CLAVE_SESION)
  set({ s: null, q: '' })
}
if (sesionGuardada) programarCaducidad(sesionGuardada.expira_en)
export const setQ = (q) => set({ q })

/* --- eventos simulados (SNS/SQS) --- */
const notif = (n, tipo, titulo, mensaje, dest) => n.notificaciones.unshift({ tenant_id: state.s.tenant_id, notificacion_id: nid('not'), usuario_destino_id: dest.u || null, rol_destino: dest.r || null, tipo, titulo, mensaje, leida: false, fecha_creacion: ahora() })
const auto = (n, o, titulo, tipo = 'tarea') => n.actividades.push({ tenant_id: state.s.tenant_id, actividad_id: nid('act'), tipo, titulo, descripcion: '', cliente_id: o.cliente_id, oportunidad_id: o.oportunidad_id, responsable_id: o.responsable_id, fecha_programada: new Date(Date.now() + 3 * 864e5).toISOString(), estado: 'pendiente', origen: 'automatica', fecha_creacion: ahora() })
const mover = (n, id, etapa, motivo = '') => {
  const o = n.oportunidades.find((x) => x.oportunidad_id === id)
  n.historial.push({ tenant_id: state.s.tenant_id, historial_id: nid('his'), oportunidad_id: id, etapa_anterior: o.etapa, etapa_nueva: etapa, usuario_id: state.s.usuario_id, fecha_cambio: ahora() })
  o.etapa = etapa; o.fecha_actualizacion = ahora()
  if (etapa === 'ganada') { auto(n, o, `Iniciar servicio: ${o.titulo}`); notif(n, 'oportunidad.ganada', '¡Oportunidad ganada!', `${o.titulo} por ${soles(o.monto_estimado, o.moneda)}`, { r: 'gerente' }); notif(n, 'oportunidad.ganada', '¡Oportunidad ganada!', o.titulo, { u: o.responsable_id }) }
  else if (etapa === 'perdida') { o.motivo_perdida = motivo; n.actividades.forEach((a) => { if (a.oportunidad_id === id && a.estado === 'pendiente') a.estado = 'cancelada' }); notif(n, 'oportunidad.perdida', 'Oportunidad perdida', `${o.titulo}: ${motivo}`, { r: 'gerente' }) }
  else { auto(n, o, `Seguimiento: ${o.titulo} pasó a ${txt(etapa)}`); notif(n, 'oportunidad.etapa_cambiada', 'Cambio de etapa', `${o.titulo} → ${txt(etapa)}`, { u: o.responsable_id }) }
}
const T = () => state.s.tenant_id, U = () => state.s.usuario_id
export const acc = {
  cliente: (v) => M((n) => { n.clientes.push({ ...v, tenant_id: T(), cliente_id: nid('cli'), responsable_id: U(), fecha_creacion: ahora(), fecha_actualizacion: ahora() }); notif(n, 'cliente.creado', 'Nuevo cliente', v.nombre, { u: U() }) }, 'Cliente creado'),
  delCliente: (id) => M((n) => { n.clientes = n.clientes.filter((c) => c.cliente_id !== id) }, 'Cliente eliminado'),
  contacto: (cid, v) => M((n) => { n.contactos.push({ ...v, tenant_id: T(), contacto_id: nid('con'), cliente_id: cid, es_principal: !n.contactos.some((c) => c.cliente_id === cid), fecha_creacion: ahora() }) }, 'Contacto agregado'),
  opo: (v) => M((n) => { n.oportunidades.push({ ...v, monto_estimado: +v.monto_estimado, fecha_cierre_estimada: new Date(v.fecha_cierre_estimada).toISOString(), tenant_id: T(), oportunidad_id: nid('opo'), etapa: 'nueva', responsable_id: U(), fecha_creacion: ahora(), fecha_actualizacion: ahora() }); notif(n, 'oportunidad.creada', 'Nueva oportunidad', v.titulo, { u: U() }) }, 'Oportunidad creada'),
  etapa: (id, e, m) => M((n) => mover(n, id, e, m), `Etapa: ${txt(e)}`),
  act: (v) => M((n) => { n.actividades.push({ ...v, oportunidad_id: v.oportunidad_id || null, tenant_id: T(), actividad_id: nid('act'), fecha_programada: new Date(v.fecha_programada).toISOString(), responsable_id: U(), estado: 'pendiente', origen: 'manual', fecha_creacion: ahora() }) }, 'Actividad creada'),
  completar: (id) => M((n) => { n.actividades.find((a) => a.actividad_id === id).estado = 'completada' }, 'Actividad completada'),
  prod: (v) => M((n) => { n.productos.push({ ...v, precio: +v.precio, tenant_id: T(), producto_id: nid('pro'), estado: 'activo', fecha_creacion: ahora() }) }, 'Producto creado'),
  togProd: (id) => M((n) => { const p = n.productos.find((x) => x.producto_id === id); p.estado = p.estado === 'activo' ? 'inactivo' : 'activo' }),
  cot: (c) => M((n) => { n.cotizaciones.push({ ...c, tenant_id: T(), cotizacion_id: nid('cot'), estado: 'borrador', creada_por: U(), fecha_creacion: ahora() }) }, 'Cotización creada'),
  estadoCot: (id, e) => M((n) => {
    const c = n.cotizaciones.find((x) => x.cotizacion_id === id), o = n.oportunidades.find((x) => x.oportunidad_id === c.oportunidad_id); c.estado = e
    if (e === 'enviada') { auto(n, o, `Dar seguimiento a cotización ${id}`, 'llamada'); notif(n, 'cotizacion.enviada', 'Cotización enviada', `${id} por ${soles(c.total)}`, { r: 'gerente' }) }
    if (e === 'rechazada') notif(n, 'cotizacion.rechazada', 'Cotización rechazada', id, { u: o.responsable_id })
    if (e === 'aceptada') { notif(n, 'cotizacion.aceptada', 'Cotización aceptada', id, { r: 'gerente' }); mover(n, o.oportunidad_id, 'ganada') }
  }, 'Cotización actualizada'),
  leer: (id) => M((n) => { n.notificaciones.find((x) => x.notificacion_id === id).leida = true }),
  usuario: (v) => M((n) => { const id = nid('usr'); n.usuarios.push({ ...v, tenant_id: T(), usuario_id: id, contrasena_hash: v.contrasena, estado: 'activo', fecha_creacion: ahora() }); notif(n, 'usuario.creado', `¡Bienvenido, ${v.nombre}!`, 'Tu cuenta está lista.', { u: id }) }, 'Usuario creado'),
  editUsuario: (id, ch) => M((n) => Object.assign(n.usuarios.find((u) => u.usuario_id === id), ch), 'Usuario actualizado'),
}

/* ============ Hook: datos del tenant de la sesión ============ */
const subir = () => state
export const useCrm = () => {
  const st = useSyncExternalStore(subscribe, subir)
  const { db, s } = st
  if (!s) return { ...st, acc }
  const mine = (k) => db[k].filter((x) => x.tenant_id === s.tenant_id) // el tenant sale siempre de la sesión
  const D = Object.fromEntries(['usuarios', 'clientes', 'contactos', 'oportunidades', 'historial', 'actividades', 'productos', 'cotizaciones'].map((k) => [k, mine(k)]))
  const misAvisos = mine('notificaciones').filter((n) => n.usuario_destino_id === s.usuario_id || n.rol_destino === s.rol)
  return {
    ...st, acc, D, misAvisos, sinLeer: misAvisos.filter((n) => !n.leida).length,
    tenant: db.tenants.find((t) => t.tenant_id === s.tenant_id),
    nom: (id) => D.usuarios.find((u) => u.usuario_id === id)?.nombre || '—',
    cli: (id) => D.clientes.find((c) => c.cliente_id === id)?.nombre || '—',
    esVend: s.rol === 'vendedor', esAdmin: s.rol === 'admin',
  }
}
