import { useEffect, useState } from 'react'
import { cotizacionesApi, productosApi } from '../productosApi'
import { aplicarResultadoAceptacion } from '../aceptacionCotizacion'
import { oportunidadesApi } from '../apiComercial'
import { useCrm, dia, soles } from '../store'
import { Cabecera, Insignia, Modal, Tabla } from '../ui'

function CotForm({ onClose, onGuardada }) {
  const [oportunidades, setOportunidades] = useState([])
  const [productos, setProductos] = useState([])
  const [cursorOportunidades, setCursorOportunidades] = useState(null)
  const [cursorProductos, setCursorProductos] = useState(null)
  const [opo, setOpo] = useState('')
  const [moneda, setMoneda] = useState('PEN')
  const [items, setItems] = useState([])
  const [prod, setProd] = useState('')
  const [venc, setVenc] = useState('')
  const [cargando, setCargando] = useState(true)
  const [cargandoMas, setCargandoMas] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const cargar = async () => {
    setCargando(true); setError('')
    try {
      const [o, p] = await Promise.all([oportunidadesApi.listar(), productosApi.listar()])
      setOportunidades(o.oportunidades); setCursorOportunidades(o.siguiente)
      setProductos(p.productos); setCursorProductos(p.siguiente)
    } catch (e) { setError(e.message || 'No se pudieron cargar los datos de la cotización.') }
    finally { setCargando(false) }
  }
  useEffect(() => { cargar() }, [])
  const masOportunidades = async () => {
    setCargandoMas('oportunidades'); setError('')
    try { const datos = await oportunidadesApi.listar(cursorOportunidades); setOportunidades(a => [...a, ...datos.oportunidades]); setCursorOportunidades(datos.siguiente) }
    catch (e) { setError(e.message || 'No se pudieron cargar más oportunidades.') }
    finally { setCargandoMas('') }
  }
  const masProductos = async () => {
    setCargandoMas('productos'); setError('')
    try { const datos = await productosApi.listar(cursorProductos); setProductos(a => [...a, ...datos.productos]); setCursorProductos(datos.siguiente) }
    catch (e) { setError(e.message || 'No se pudieron cargar más productos.') }
    finally { setCargandoMas('') }
  }
  const abiertas = oportunidades.filter(o => !['ganada', 'perdida'].includes(o.etapa))
  const disponibles = productos.filter(p => p.estado === 'activo' && p.moneda === moneda && !items.some(i => i.producto_id === p.producto_id))
  const agregar = () => {
    const p = disponibles.find(x => x.producto_id === prod)
    if (!p) { setError('Selecciona un producto activo de la moneda elegida.'); return }
    if (items.length >= 50) { setError('Una cotización admite hasta 50 productos.'); return }
    setItems(a => [...a, { producto_id: p.producto_id, nombre: p.nombre, precio: p.precio, cantidad: 1 }])
    setProd(''); setError('')
  }
  const guardar = async e => {
    e.preventDefault(); setError('')
    const oportunidad = abiertas.find(o => o.oportunidad_id === opo)
    if (!oportunidad || !items.length || items.some(i => !Number.isInteger(i.cantidad) || i.cantidad < 1 || i.cantidad > 100000)) {
      setError('Selecciona una oportunidad abierta y productos con cantidades enteras entre 1 y 100 000.'); return
    }
    const datos = { oportunidad_id: opo, cliente_id: oportunidad.cliente_id, moneda,
      items: items.map(i => ({ producto_id: i.producto_id, cantidad: i.cantidad })) }
    if (venc) {
      const fecha = new Date(`${venc}T23:59:59`)
      if (Number.isNaN(fecha.getTime()) || fecha.getTime() <= Date.now()) { setError('El vencimiento debe ser una fecha futura.'); return }
      datos.fecha_vencimiento = fecha.toISOString()
    }
    setGuardando(true)
    try { await cotizacionesApi.crear(datos); onGuardada() }
    catch (e) { setError(e.message || 'No se pudo crear la cotización.') }
    finally { setGuardando(false) }
  }
  const total = items.reduce((a, i) => a + i.precio * i.cantidad, 0)
  return <Modal titulo="Nueva cotización" onClose={() => !guardando && onClose()} ancho={600}>
    {error && <div className="error" role="alert">{error}</div>}
    {cargando ? <div className="vacio">Cargando oportunidades y productos…</div> : <form className="form" onSubmit={guardar}>
      <label>Oportunidad<select required value={opo} onChange={e => setOpo(e.target.value)}><option value="">Selecciona una oportunidad abierta</option>
        {abiertas.map(o => <option key={o.oportunidad_id} value={o.oportunidad_id}>{o.titulo} · {o.cliente_nombre || o.cliente_id}</option>)}</select></label>
      {cursorOportunidades && <button type="button" className="btn" disabled={Boolean(cargandoMas)} onClick={masOportunidades}>{cargandoMas === 'oportunidades' ? 'Cargando…' : 'Cargar más oportunidades'}</button>}
      <label>Moneda<select value={moneda} onChange={e => { setMoneda(e.target.value); setItems([]); setProd('') }}><option>PEN</option><option>USD</option></select></label>
      <label>Válida hasta (opcional)<input type="date" value={venc} onChange={e => setVenc(e.target.value)} /></label>
      <div className="acciones"><select value={prod} onChange={e => setProd(e.target.value)} aria-label="Producto"><option value="">Selecciona un producto</option>
        {disponibles.map(p => <option key={p.producto_id} value={p.producto_id}>{p.nombre} · {soles(p.precio, p.moneda)}</option>)}</select>
        <button type="button" className="btn mini" onClick={agregar}>＋ Agregar ítem</button></div>
      {cursorProductos && <button type="button" className="btn" disabled={Boolean(cargandoMas)} onClick={masProductos}>{cargandoMas === 'productos' ? 'Cargando…' : 'Cargar más productos'}</button>}
      {!abiertas.length && <p className="nota">Necesitas una oportunidad abierta; puedes cargar más páginas.</p>}
      {!disponibles.length && !items.length && <p className="nota">No hay productos activos cargados para esta moneda.</p>}
      {items.map(i => <div className="fila" key={i.producto_id}><span>{i.nombre}</span>
        <input aria-label={`Cantidad de ${i.nombre}`} className="cant" type="number" min="1" max="100000" step="1" value={i.cantidad} onChange={e => setItems(a => a.map(x => x.producto_id === i.producto_id ? { ...x, cantidad: Number(e.target.value) } : x))} />
        <b>{soles(i.precio * i.cantidad, moneda)}</b><button type="button" className="btn mini" onClick={() => setItems(a => a.filter(x => x.producto_id !== i.producto_id))}>Quitar</button></div>)}
      <h3 className="total">Total estimado: {soles(total, moneda)}</h3><p className="nota">El servicio calcula el total definitivo al guardar. Si no eliges vencimiento, usa 15 días.</p>
      <button className="btn pri" disabled={guardando || !opo || !items.length}>{guardando ? 'Guardando…' : 'Crear cotización'}</button>
    </form>}
  </Modal>
}

export default function Cotizaciones() {
  const { esVend } = useCrm()
  const [cotizaciones, setCotizaciones] = useState([])
  const [siguiente, setSiguiente] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [cargandoMas, setCargandoMas] = useState(false)
  const [actualizando, setActualizando] = useState(null)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const [errorSeguimiento, setErrorSeguimiento] = useState('')
  const [modal, setModal] = useState(false)
  const cargar = async () => {
    setCargando(true); setError('')
    try { const datos = await cotizacionesApi.listar(); setCotizaciones(datos.cotizaciones); setSiguiente(datos.siguiente) }
    catch (e) { setError(e.message || 'No se pudieron cargar las cotizaciones.') }
    finally { setCargando(false) }
  }
  useEffect(() => { cargar() }, [])
  const pendientes = cotizaciones.filter(c => c.estado === 'aceptacion_pendiente').map(c => c.cotizacion_id).sort().join(',')
  useEffect(() => {
    if (!pendientes) return
    let activa = true
    const revisar = async () => {
      const ids = pendientes.split(',')
      const resultados = await Promise.allSettled(ids.map(cotizacionesApi.obtener))
      if (!activa) return
      setErrorSeguimiento(resultados.some(r => r.status === 'rejected')
        ? 'No se pudo consultar alguna aceptación pendiente. La consulta se reintentará automáticamente.' : '')
      setCotizaciones(actuales => actuales.map(c => {
        const indice = ids.indexOf(c.cotizacion_id)
        if (indice < 0 || c.estado !== 'aceptacion_pendiente' || resultados[indice].status !== 'fulfilled') return c
        return aplicarResultadoAceptacion(c, resultados[indice].value.cotizacion)
      }))
    }
    revisar()
    const intervalo = setInterval(revisar, 15000)
    return () => { activa = false; clearInterval(intervalo) }
  }, [pendientes])
  const mas = async () => {
    setCargandoMas(true); setError('')
    try { const datos = await cotizacionesApi.listar(siguiente); setCotizaciones(a => [...a, ...datos.cotizaciones]); setSiguiente(datos.siguiente) }
    catch (e) { setError(e.message || 'No se pudieron cargar más cotizaciones.') }
    finally { setCargandoMas(false) }
  }
  const actuar = async (c, accion) => {
    if (accion === 'archivar' && !window.confirm('¿Archivar esta cotización?')) return
    setActualizando(c.cotizacion_id); setError(''); setAviso('')
    try {
      const resultado = await cotizacionesApi[accion](c.cotizacion_id)
      if (accion === 'aceptar') {
        setCotizaciones(a => a.map(item => item.cotizacion_id === c.cotizacion_id
          ? { ...item, estado: 'aceptacion_pendiente', resultado_aceptacion: '', fecha_solicitud_aceptacion: resultado.fecha_solicitud, _solicitudAnterior: c.solicitud_aceptacion_id || null } : item))
        setAviso('Aceptación solicitada. Espera la confirmación; puede tardar varios minutos.')
      } else if (accion === 'archivar') {
        setCotizaciones(a => a.filter(item => item.cotizacion_id !== c.cotizacion_id))
        setAviso('Cotización archivada.')
      } else {
        setCotizaciones(a => a.map(item => item.cotizacion_id === c.cotizacion_id ? { ...item, estado: resultado.estado } : item))
        setAviso(resultado.mensaje || 'Cotización actualizada.')
      }
    } catch (e) { setError(e.message || 'No se pudo actualizar la cotización.') }
    finally { setActualizando(null) }
  }
  return <>
    <Cabecera t="Cotizaciones" sub="Ofertas formales para tus oportunidades">
      <button className="btn" onClick={cargar} disabled={cargando}>↻ Actualizar</button>
      <button className="btn pri" onClick={() => setModal(true)}>＋ Nueva cotización</button>
    </Cabecera>
    {error && <div className="error" role="alert">{error}</div>}
    {pendientes && errorSeguimiento && <div className="error" role="alert">{errorSeguimiento}</div>}
    {aviso && <p role="status" className="nota">{aviso}</p>}
    {cargando ? <div className="vacio">Cargando cotizaciones…</div> : <>
      <Tabla vacio="No hay cotizaciones en esta página." rows={cotizaciones}
        cols={[
          ['Código', c => c.cotizacion_id], ['Oportunidad', c => c.oportunidad_id],
          ['Ítems', c => c.items?.length ?? 0], ['Total', c => <b>{soles(c.total, c.moneda)}</b>],
          ['Vence', c => dia(c.fecha_vencimiento)],
          ['Estado', c => <div><Insignia v={c.estado} />{c.estado === 'aceptacion_pendiente' && <small> Esperando confirmación…</small>}{c.estado === 'aceptacion_pendiente' && c.fecha_solicitud_aceptacion && Date.now() - Date.parse(c.fecha_solicitud_aceptacion) >= 30 * 60 * 1000 && <p className="error" role="status">La confirmación está tardando más de lo esperado. Contacta a soporte.</p>}{c.resultado_aceptacion && <p className="error" role="status">{c.resultado_aceptacion}</p>}</div>],
          ['Acciones', c => <div className="acciones">
            {c.estado === 'borrador' && <button className="btn mini" disabled={Boolean(actualizando)} onClick={() => actuar(c, 'enviar')}>Enviar</button>}
            {c.estado === 'enviada' && <><button className="btn mini ok" disabled={Boolean(actualizando)} onClick={() => actuar(c, 'aceptar')}>Aceptar</button><button className="btn mini no" disabled={Boolean(actualizando)} onClick={() => actuar(c, 'rechazar')}>Rechazar</button></>}
            {!esVend && !['aceptada', 'aceptacion_pendiente'].includes(c.estado) && <button className="btn mini" disabled={Boolean(actualizando)} onClick={() => actuar(c, 'archivar')}>Archivar</button>}
          </div>],
        ]} />
      {siguiente && <button className="btn" disabled={cargandoMas} onClick={mas}>{cargandoMas ? 'Cargando…' : 'Cargar más cotizaciones'}</button>}
      {pendientes && <p className="nota">La aceptación se consulta automáticamente. Si permanece pendiente durante mucho tiempo, contacta a soporte.</p>}
    </>}
    {modal && <CotForm onClose={() => setModal(false)} onGuardada={() => { setModal(false); cargar() }} />}
  </>
}
