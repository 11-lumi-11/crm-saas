import { useEffect, useState } from 'react'
import { clientesApi } from '../clientesApi'
import { useCrm } from '../store'
import { Cabecera, Form, Insignia, Modal, Tabla } from '../ui'

const camposCliente = (cliente = {}) => [
  { k: 'nombre', l: 'Razón social o nombre', d: cliente.nombre || '' },
  { k: 'tipo', l: 'Tipo', o: ['empresa', 'persona'], d: cliente.tipo || 'empresa' },
  { k: 'documento', l: 'RUC o DNI', d: cliente.documento || '', r: false },
  { k: 'correo', l: 'Correo', t: 'email', d: cliente.correo || '', r: false },
  { k: 'telefono', l: 'Teléfono', d: cliente.telefono || '', r: false },
  { k: 'industria', l: 'Industria', d: cliente.industria || '', r: false },
  { k: 'ciudad', l: 'Ciudad', d: cliente.ciudad || '', r: false },
  { k: 'estado', l: 'Estado', o: ['prospecto', 'activo', 'inactivo'], d: cliente.estado || 'prospecto' },
]

function FormularioCliente({ cliente, onClose, onGuardado }) {
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const guardar = async (datos) => {
    setGuardando(true); setError('')
    try {
      if (cliente) await clientesApi.actualizar(cliente.cliente_id, datos)
      else await clientesApi.crear(datos)
      onGuardado()
    } catch (e) { setError(e.message || 'No se pudo guardar el cliente.') }
    finally { setGuardando(false) }
  }
  return <Modal titulo={cliente ? 'Editar cliente' : 'Nuevo cliente'} onClose={onClose}>
    {error && <div className="error" role="alert">{error}</div>}
    <Form f={camposCliente(cliente)} onSubmit={guardar} disabled={guardando} ok={guardando ? 'Guardando…' : 'Guardar'} />
  </Modal>
}

function FormularioContacto({ tienePrincipal, onGuardar, guardando }) {
  const [datos, setDatos] = useState({ nombre: '', cargo: '', correo: '', telefono: '', es_principal: false })
  const cambiar = (campo, valor) => setDatos(actual => ({ ...actual, [campo]: valor }))
  const enviar = async (event) => {
    event.preventDefault()
    if (await onGuardar(datos)) setDatos({ nombre: '', cargo: '', correo: '', telefono: '', es_principal: false })
  }
  return <form className="form" onSubmit={enviar}>
    <label>Nombre<input required value={datos.nombre} onChange={e => cambiar('nombre', e.target.value)} /></label>
    <label>Cargo<input value={datos.cargo} onChange={e => cambiar('cargo', e.target.value)} /></label>
    <label>Correo<input type="email" value={datos.correo} onChange={e => cambiar('correo', e.target.value)} /></label>
    <label>Teléfono<input value={datos.telefono} onChange={e => cambiar('telefono', e.target.value)} /></label>
    <label><input type="checkbox" checked={datos.es_principal} disabled={tienePrincipal || guardando}
      onChange={e => cambiar('es_principal', e.target.checked)} /> Contacto principal</label>
    {tienePrincipal && <small>Este cliente ya tiene un contacto principal.</small>}
    <button className="btn pri" disabled={guardando}>{guardando ? 'Guardando…' : 'Agregar contacto'}</button>
  </form>
}

function Ficha({ id, onClose, onCambio }) {
  const { s } = useCrm()
  const [cliente, setCliente] = useState(null)
  const [contactos, setContactos] = useState([])
  const [siguiente, setSiguiente] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [cargandoMas, setCargandoMas] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const [editando, setEditando] = useState(false)
  const cargar = async () => {
    setCargando(true); setError('')
    try {
      const [datos, lista] = await Promise.all([clientesApi.obtener(id), clientesApi.contactos(id)])
      setCliente(datos.cliente); setContactos(lista.contactos); setSiguiente(lista.siguiente)
    } catch (e) { setError(e.message || 'No se pudo cargar el cliente.') }
    finally { setCargando(false) }
  }
  useEffect(() => { cargar() }, [id])
  const masContactos = async () => {
    setCargandoMas(true); setError('')
    try {
      const lista = await clientesApi.contactos(id, siguiente)
      setContactos(actual => [...actual, ...lista.contactos]); setSiguiente(lista.siguiente)
    } catch (e) { setError(e.message || 'No se pudieron cargar más contactos.') }
    finally { setCargandoMas(false) }
  }
  const agregarContacto = async (datos) => {
    setGuardando(true); setError('')
    try {
      await clientesApi.crearContacto(id, datos)
      await cargar()
      return true
    } catch (e) { setError(e.message || 'No se pudo crear el contacto.'); return false }
    finally { setGuardando(false) }
  }
  const responsable = cliente?.responsable_id === s.usuario_id ? 'Tú' : cliente?.responsable_id || '—'
  return <Modal titulo={cliente?.nombre || 'Detalle del cliente'} onClose={onClose} ancho={620}>
    {error && <div className="error" role="alert">{error}</div>}
    {cargando ? <div className="vacio">Cargando cliente…</div> : !cliente ?
      <button className="btn" onClick={cargar}>Reintentar</button> : <>
        <div className="ficha">{[['Documento', cliente.documento], ['Correo', cliente.correo], ['Teléfono', cliente.telefono],
          ['Industria', cliente.industria], ['Ciudad', cliente.ciudad], ['Responsable', responsable]].map(([k, v]) =>
          <div key={k}><small>{k}</small>{v || '—'}</div>)}</div>
        <div className="acciones"><button className="btn" onClick={() => setEditando(true)}>Editar cliente</button></div>
        <h4>Contactos</h4>
        {contactos.length ? contactos.map(c => <div className="fila" key={c.contacto_id}>
          <span>{c.nombre}{c.cargo && ` · ${c.cargo}`} {c.es_principal && <Insignia v="principal" />}</span>
          <small>{c.correo || c.telefono || ''}</small></div>) : <div className="vacio">Aún no hay contactos.</div>}
        {siguiente && <button className="btn" disabled={cargandoMas} onClick={masContactos}>
          {cargandoMas ? 'Cargando…' : 'Cargar más contactos'}</button>}
        <h4>Agregar contacto</h4>
        <FormularioContacto tienePrincipal={Boolean(cliente.contacto_principal_id)} onGuardar={agregarContacto} guardando={guardando} />
        {editando && <FormularioCliente cliente={cliente} onClose={() => setEditando(false)} onGuardado={() => {
          setEditando(false); cargar(); onCambio()
        }} />}
      </>}
  </Modal>
}

export default function Clientes() {
  const { q } = useCrm()
  const [clientes, setClientes] = useState([])
  const [siguiente, setSiguiente] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [cargandoMas, setCargandoMas] = useState(false)
  const [error, setError] = useState('')
  const [m, setM] = useState(null)
  const cargar = async () => {
    setCargando(true); setError('')
    try {
      const datos = await clientesApi.listar()
      setClientes(datos.clientes); setSiguiente(datos.siguiente)
    } catch (e) { setError(e.message || 'No se pudieron cargar los clientes.') }
    finally { setCargando(false) }
  }
  useEffect(() => { cargar() }, [])
  const mas = async () => {
    setCargandoMas(true); setError('')
    try {
      const datos = await clientesApi.listar(siguiente)
      setClientes(actual => [...actual, ...datos.clientes]); setSiguiente(datos.siguiente)
    } catch (e) { setError(e.message || 'No se pudieron cargar más clientes.') }
    finally { setCargandoMas(false) }
  }
  const busqueda = q.toLowerCase().trim()
  const rows = clientes.filter(c => [c.nombre, c.ciudad, c.industria].some(v => (v || '').toLowerCase().includes(busqueda)))
  return <>
    <Cabecera t="Clientes" sub="Cuentas y contactos de tu empresa"><button className="btn pri" onClick={() => setM('nuevo')}>＋ Nuevo cliente</button></Cabecera>
    {error && <div className="error" role="alert">{error} <button className="btn mini" onClick={cargar}>Reintentar</button></div>}
    {cargando ? <div className="vacio">Cargando clientes…</div> : !error && <>
      <Tabla vacio={busqueda ? 'No hay coincidencias entre los clientes cargados.' : 'Aún no hay clientes en esta página.'} rows={rows} onRow={c => setM(c.cliente_id)}
        cols={[
          ['Nombre', c => <b>{c.nombre}</b>], ['Tipo', c => c.tipo], ['Industria', c => c.industria || '—'],
          ['Ciudad', c => c.ciudad || '—'], ['Estado', c => <Insignia v={c.estado} />], ['Responsable', c => c.responsable_id],
        ]} />
      {siguiente && <button className="btn" disabled={cargandoMas} onClick={mas}>{cargandoMas ? 'Cargando…' : 'Cargar más clientes'}</button>}
      {siguiente && busqueda && <small>La búsqueda solo incluye los clientes cargados.</small>}
    </>}
    {m === 'nuevo' && <FormularioCliente onClose={() => setM(null)} onGuardado={() => { setM(null); cargar() }} />}
    {m && m !== 'nuevo' && <Ficha id={m} onClose={() => setM(null)} onCambio={cargar} />}
  </>
}
