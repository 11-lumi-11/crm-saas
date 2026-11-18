import { BotonActualizar } from '../ui'
import { useCacheVista, invalidarVistas } from '../cacheVistas'
import { useEffect, useState } from 'react'
import { productosApi } from '../productosApi'
import { useCrm, soles } from '../store'
import { Cabecera, Insignia, Modal } from '../ui'

function ProductoForm({ producto, onClose, onGuardado }) {
  const [nombre, setNombre] = useState(producto?.nombre || '')
  const [descripcion, setDescripcion] = useState(producto?.descripcion || '')
  const [categoria, setCategoria] = useState(producto?.categoria || '')
  const [precio, setPrecio] = useState(producto ? String(producto.precio) : '')
  const [moneda, setMoneda] = useState(producto?.moneda || 'PEN')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const enviar = async e => {
    e.preventDefault(); setError('')
    const valor = Number(precio)
    if (!nombre.trim() || precio === '' || !Number.isFinite(valor) || valor < 0 || valor > 1e12) {
      setError('Ingresa un nombre y un precio entre 0 y 1 000 000 000 000.'); return
    }
    const datos = { nombre: nombre.trim(), descripcion, categoria, precio: valor, moneda }
    setGuardando(true)
    try {
      if (producto) await productosApi.actualizar(producto.producto_id, datos)
      else await productosApi.crear(datos)
      onGuardado()
    } catch (e) { setError(e.message || 'No se pudo guardar el producto.') }
    finally { setGuardando(false) }
  }
  return <Modal titulo={producto ? 'Editar producto' : 'Nuevo producto'} onClose={() => !guardando && onClose()}>
    {error && <div className="error" role="alert">{error}</div>}
    <form className="form" onSubmit={enviar}>
      <label>Nombre<input required value={nombre} onChange={e => setNombre(e.target.value)} /></label>
      <label>Descripción<input value={descripcion} onChange={e => setDescripcion(e.target.value)} /></label>
      <label>Categoría<input value={categoria} onChange={e => setCategoria(e.target.value)} /></label>
      <label>Precio<input required type="number" min="0" max="1000000000000" step="0.01" value={precio} onChange={e => setPrecio(e.target.value)} /></label>
      <label>Moneda<select value={moneda} onChange={e => setMoneda(e.target.value)}><option>PEN</option><option>USD</option></select></label>
      <button className="btn pri" disabled={guardando}>{guardando ? 'Guardando…' : 'Guardar'}</button>
    </form>
  </Modal>
}

export default function Productos({ activa }) {
  const { esVend } = useCrm()
  const [productos, setProductos] = useState([])
  const [siguiente, setSiguiente] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [cargandoMas, setCargandoMas] = useState(false)
  const [actualizando, setActualizando] = useState(null)
  const [error, setError] = useState('')
  const [modal, setModal] = useState(null)
  const cargar = async () => {
    const carga = cache.iniciarCarga()
    if (!cache.estado.current.cargada) setCargando(true); setError('')
    try { const datos = await productosApi.listar(); if (!cache.esActual(carga)) return; setProductos(datos.productos); setSiguiente(datos.siguiente); cache.registrarCarga(carga) }
    catch (e) { setError(e.message || 'No se pudieron cargar los productos.') }
    finally { setCargando(false) }
  }
  const cache = useCacheVista('productos', activa, cargar)
  const mas = async () => {
    setCargandoMas(true); setError('')
    try { const datos = await productosApi.listar(siguiente); setProductos(a => [...a, ...datos.productos]); setSiguiente(datos.siguiente) }
    catch (e) { setError(e.message || 'No se pudieron cargar más productos.') }
    finally { setCargandoMas(false) }
  }
  const cambiarEstado = async p => {
    setActualizando(p.producto_id); setError('')
    try {
      const datos = await productosApi.actualizar(p.producto_id, { estado: p.estado === 'activo' ? 'inactivo' : 'activo' })
      setProductos(a => a.map(item => item.producto_id === p.producto_id ? datos.producto : item)); invalidarVistas('cotizaciones')
    } catch (e) { setError(e.message || 'No se pudo cambiar el estado del producto.') }
    finally { setActualizando(null) }
  }
  return <>
    <Cabecera t="Productos" sub="Catálogo de lo que vende tu empresa">
      <BotonActualizar onActualizar={cargar} disabled={cargando} />
      {!esVend && <button className="btn pri" onClick={() => setModal('nuevo')}>＋ Nuevo producto</button>}
    </Cabecera>
    {error && <div className="error" role="alert">{error}</div>}
    {cargando ? <div className="vacio">Cargando productos…</div> : <>
      <div className="grid">{productos.map(p => <div className={`tarjeta ${p.estado}`} key={p.producto_id}>
        <Insignia v={p.estado} /><h3>{p.nombre}</h3><p>{p.descripcion}</p><small>{p.categoria}</small><strong>{soles(p.precio, p.moneda)}</strong>
        {!esVend && <div className="acciones">
          <button className="btn mini" disabled={Boolean(actualizando)} onClick={() => setModal(p)}>Editar</button>
          <button className="btn mini" disabled={Boolean(actualizando)} onClick={() => cambiarEstado(p)}>
            {actualizando === p.producto_id ? 'Guardando…' : p.estado === 'activo' ? 'Desactivar' : 'Activar'}</button>
        </div>}
      </div>)}</div>
      {!productos.length && <div className="vacio">No hay productos en esta página.</div>}
      {siguiente && <button className="btn" disabled={cargandoMas} onClick={mas}>{cargandoMas ? 'Cargando…' : 'Cargar más productos'}</button>}
    </>}
    {modal && <ProductoForm producto={modal === 'nuevo' ? null : modal} onClose={() => setModal(null)} onGuardado={() => { setModal(null); invalidarVistas('cotizaciones'); cargar() }} />}
  </>
}
