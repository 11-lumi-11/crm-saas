import { useEffect, useState } from 'react'
import { oportunidadesApi } from '../apiComercial'
import { clientesApi } from '../clientesApi'
import { ETAPAS, txt, dia, soles } from '../store'
import { Cabecera, Insignia, Modal } from '../ui'

function Nueva({ clientes, siguiente, cargarMas, cargandoMas, errorClientes, onClose, onGuardada }) {
  const [titulo, setTitulo] = useState('')
  const [clienteId, setClienteId] = useState(clientes[0]?.cliente_id || '')
  const [monto, setMonto] = useState('')
  const [moneda, setMoneda] = useState('PEN')
  const [fecha, setFecha] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const enviar = async e => {
    e.preventDefault(); setError('')
    const numero = Number(monto)
    if (!titulo.trim() || !clienteId || monto === '' || !Number.isFinite(numero) || numero < 0 || numero > 1e12) {
      setError('Ingresa un título, cliente y monto entre 0 y 1 000 000 000 000.'); return
    }
    const cliente = clientes.find(c => c.cliente_id === clienteId)
    if (!cliente) { setError('Selecciona un cliente válido.'); return }
    const datos = { titulo: titulo.trim(), cliente_id: clienteId, cliente_nombre: cliente.nombre, monto_estimado: numero, moneda }
    if (fecha) datos.fecha_cierre_estimada = new Date(`${fecha}T12:00:00Z`).toISOString()
    setGuardando(true)
    try { await oportunidadesApi.crear(datos); onGuardada() }
    catch (e) { setError(e.message || 'No se pudo crear la oportunidad.') }
    finally { setGuardando(false) }
  }
  return <Modal titulo="Nueva oportunidad" onClose={onClose}>
    {error && <div className="error" role="alert">{error}</div>}
    {errorClientes && <div className="error" role="alert">{errorClientes}</div>}
    {!clientes.length && <div className="vacio">No hay clientes cargados. Crea uno o carga la siguiente página.</div>}
    <form className="form" onSubmit={enviar}>
      <label>Título<input required value={titulo} onChange={e => setTitulo(e.target.value)} /></label>
      <label>Cliente<select required value={clienteId} onChange={e => setClienteId(e.target.value)}>
        <option value="">Selecciona un cliente</option>
        {clientes.map(c => <option key={c.cliente_id} value={c.cliente_id}>{c.nombre}</option>)}
      </select></label>
      {siguiente && <button type="button" className="btn" disabled={cargandoMas} onClick={cargarMas}>{cargandoMas ? 'Cargando…' : 'Cargar más clientes'}</button>}
      <label>Monto estimado<input type="number" required min="0" max="1000000000000" step="0.01" value={monto} onChange={e => setMonto(e.target.value)} /></label>
      <label>Moneda<select value={moneda} onChange={e => setMoneda(e.target.value)}><option>PEN</option><option>USD</option></select></label>
      <label>Cierre estimado (opcional)<input type="date" value={fecha} onChange={e => setFecha(e.target.value)} /></label>
      <button className="btn pri" disabled={guardando || !clienteId}>{guardando ? 'Guardando…' : 'Crear oportunidad'}</button>
    </form>
  </Modal>
}

function Detalle({ id, clientes, onClose, onCambio }) {
  const [o, setO] = useState(null)
  const [historial, setHistorial] = useState([])
  const [cargando, setCargando] = useState(true)
  const [guardando, setGuardando] = useState(false)
  const [motivo, setMotivo] = useState('')
  const [perdiendo, setPerdiendo] = useState(false)
  const [error, setError] = useState('')
  const cargar = async () => {
    setCargando(true); setError('')
    try {
      const [dato, historia] = await Promise.all([oportunidadesApi.obtener(id), oportunidadesApi.historial(id)])
      setO(dato.oportunidad); setHistorial(historia.historial)
    } catch (e) { setError(e.message || 'No se pudo cargar la oportunidad.') }
    finally { setCargando(false) }
  }
  useEffect(() => { cargar() }, [id])
  const cambiar = async etapa => {
    if (etapa === 'perdida' && !motivo.trim()) { setError('Indica el motivo de la pérdida.'); return }
    setGuardando(true); setError('')
    try {
      const datos = etapa === 'perdida' ? { etapa, motivo_perdida: motivo.trim() } : { etapa }
      await oportunidadesApi.etapa(id, datos)
      onCambio(); onClose()
    } catch (e) { setError(e.message || 'No se pudo cambiar la etapa.') }
    finally { setGuardando(false) }
  }
  const cerrada = o && ['ganada', 'perdida'].includes(o.etapa)
  const cliente = o && (clientes.find(c => c.cliente_id === o.cliente_id)?.nombre || o.cliente_nombre || o.cliente_id)
  return <Modal titulo={o?.titulo || 'Oportunidad'} onClose={onClose}>
    {error && <div className="error" role="alert">{error}</div>}
    {cargando ? <div className="vacio">Cargando oportunidad…</div> : !o ? <button className="btn" onClick={cargar}>Reintentar</button> : <>
      <div className="ficha"><div><small>Cliente</small>{cliente}</div><div><small>Monto</small>{soles(o.monto_estimado, o.moneda)}</div><div><small>Etapa</small><Insignia v={o.etapa} /></div><div><small>Cierre estimado</small>{dia(o.fecha_cierre_estimada)}</div></div>
      {o.motivo_perdida && <p className="error">Motivo: {o.motivo_perdida}</p>}
      {cerrada ? <p className="nota">Esta oportunidad está cerrada y no se puede reabrir.</p> : <div className="acciones">
        <button className="btn no" disabled={guardando} onClick={() => setPerdiendo(true)}>Marcar perdida</button>
      </div>}
      {perdiendo && !cerrada && <form className="form" onSubmit={e => { e.preventDefault(); cambiar('perdida') }}>
        <label>Motivo de pérdida<input required value={motivo} onChange={e => setMotivo(e.target.value)} /></label>
        <button className="btn no" disabled={guardando}>{guardando ? 'Guardando…' : 'Confirmar pérdida'}</button>
      </form>}
      <h4>Historial</h4>
      {historial.map(h => <div className="fila" key={h.historial_id}><span>{txt(h.etapa_anterior)} → {txt(h.etapa_nueva)}</span><small>{h.usuario_id} · {dia(h.fecha_cambio)}</small></div>)}
      {!historial.length && <div className="vacio">Aún sin cambios de etapa.</div>}
      <button className="btn mini" onClick={cargar}>Actualizar historial</button>
    </>}
  </Modal>
}

export default function Oportunidades() {
  const [lista, setLista] = useState([])
  const [siguiente, setSiguiente] = useState(null)
  const [clientes, setClientes] = useState([])
  const [cursorClientes, setCursorClientes] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [cargandoMas, setCargandoMas] = useState(false)
  const [cargandoClientes, setCargandoClientes] = useState(false)
  const [error, setError] = useState('')
  const [errorClientes, setErrorClientes] = useState('')
  const [modal, setModal] = useState(null)
  const cargar = async () => {
    setCargando(true); setError('')
    try {
      const [o, c] = await Promise.all([oportunidadesApi.listar(), clientesApi.listar()])
      setLista(o.oportunidades); setSiguiente(o.siguiente); setClientes(c.clientes); setCursorClientes(c.siguiente)
    } catch (e) { setError(e.message || 'No se pudieron cargar las oportunidades.') }
    finally { setCargando(false) }
  }
  useEffect(() => { cargar() }, [])
  const mas = async () => {
    setCargandoMas(true); setError('')
    try { const datos = await oportunidadesApi.listar(siguiente); setLista(a => [...a, ...datos.oportunidades]); setSiguiente(datos.siguiente) }
    catch (e) { setError(e.message || 'No se pudieron cargar más oportunidades.') }
    finally { setCargandoMas(false) }
  }
  const masClientes = async () => {
    setCargandoClientes(true); setErrorClientes('')
    try { const datos = await clientesApi.listar(cursorClientes); setClientes(a => [...a, ...datos.clientes]); setCursorClientes(datos.siguiente) }
    catch (e) { setErrorClientes(e.message || 'No se pudieron cargar más clientes.') }
    finally { setCargandoClientes(false) }
  }
  return <>
    <Cabecera t="Oportunidades" sub="Pipeline de ventas por etapa"><button className="btn" onClick={cargar} disabled={cargando}>↻ Actualizar</button> <button className="btn pri" onClick={() => setModal('nueva')} disabled={cargando}>＋ Nueva oportunidad</button></Cabecera>
    {error && <div className="error" role="alert">{error} <button className="btn mini" onClick={cargar}>Reintentar</button></div>}
    {cargando ? <div className="vacio">Cargando oportunidades…</div> : <>
      <div className="kanban">{ETAPAS.map(etapa => {
        const items = lista.filter(o => o.etapa === etapa)
        return <div className="col" key={etapa}><h4><Insignia v={etapa} /> <small>{items.length}</small></h4>
          {items.map(o => <button type="button" className="col-card" key={o.oportunidad_id} onClick={() => setModal({ id: o.oportunidad_id })}>
            <b>{o.titulo}</b><span>{clientes.find(c => c.cliente_id === o.cliente_id)?.nombre || o.cliente_nombre || o.cliente_id}</span><strong>{soles(o.monto_estimado, o.moneda)}</strong>
          </button>)}
        </div>
      })}</div>
      {siguiente && <button className="btn" disabled={cargandoMas} onClick={mas}>{cargandoMas ? 'Cargando…' : 'Cargar más oportunidades'}</button>}
      <p className="nota">El tablero muestra las oportunidades cargadas. Los seguimientos automáticos pueden tardar unos minutos.</p>
    </>}
    {modal === 'nueva' && <Nueva clientes={clientes} siguiente={cursorClientes} cargarMas={masClientes} cargandoMas={cargandoClientes} errorClientes={errorClientes} onClose={() => { setModal(null); setErrorClientes('') }} onGuardada={() => { setModal(null); cargar() }} />}
    {modal?.id && <Detalle id={modal.id} clientes={clientes} onClose={() => setModal(null)} onCambio={cargar} />}
  </>
}
