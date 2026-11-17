import { useEffect, useState } from 'react'
import { actividadesApi } from '../apiComercial'
import { useCrm, dia } from '../store'
import { Cabecera, Insignia, Tabla } from '../ui'

export default function Actividades() {
  const { s, esVend } = useCrm()
  const [items, setItems] = useState([])
  const [siguiente, setSiguiente] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [cargandoMas, setCargandoMas] = useState(false)
  const [actualizando, setActualizando] = useState(null)
  const [error, setError] = useState('')
  const filtro = esVend ? { responsable_id: s.usuario_id } : {}
  const cargar = async () => {
    setCargando(true); setError('')
    try { const datos = await actividadesApi.listar(filtro); setItems(datos.actividades); setSiguiente(datos.siguiente) }
    catch (e) { setError(e.message || 'No se pudieron cargar las actividades.') }
    finally { setCargando(false) }
  }
  useEffect(() => { cargar() }, [s.usuario_id, esVend])
  const mas = async () => {
    setCargandoMas(true); setError('')
    try { const datos = await actividadesApi.listar({ ...filtro, siguiente }); setItems(a => [...a, ...datos.actividades]); setSiguiente(datos.siguiente) }
    catch (e) { setError(e.message || 'No se pudieron cargar más actividades.') }
    finally { setCargandoMas(false) }
  }
  const completar = async id => {
    setActualizando(id); setError('')
    try {
      const datos = await actividadesApi.completar(id)
      setItems(a => a.map(item => item.actividad_id === id ? datos.actividad : item))
    } catch (e) { setError(e.message || 'No se pudo completar la actividad.') }
    finally { setActualizando(null) }
  }
  return <>
    <Cabecera t="Actividades" sub="Seguimientos y tareas reales de tu empresa"><button className="btn" onClick={cargar} disabled={cargando}>↻ Actualizar</button></Cabecera>
    <p className="nota">Los seguimientos automáticos pueden tardar unos minutos en aparecer. Usa Actualizar para consultarlos.</p>
    {error && <div className="error" role="alert">{error}</div>}
    {cargando ? <div className="vacio">Cargando actividades…</div> : <>
      <Tabla vacio="No hay actividades en esta página." rows={items}
        cols={[
          ['Tipo', a => <Insignia v={a.tipo} />], ['Título', a => a.titulo], ['Cliente', a => a.cliente_id],
          ['Fecha', a => dia(a.fecha_programada)], ['Origen', a => a.origen], ['Estado', a => <Insignia v={a.estado} />],
          ['', a => a.estado === 'pendiente' && <button className="btn mini" disabled={Boolean(actualizando)} onClick={() => completar(a.actividad_id)}>{actualizando === a.actividad_id ? 'Guardando…' : '✓ Completar'}</button>],
        ]} />
      {siguiente && <button className="btn" onClick={mas} disabled={cargandoMas}>{cargandoMas ? 'Cargando…' : 'Cargar más actividades'}</button>}
    </>}
    <p className="nota">La creación y edición manual de actividades se integrarán más adelante.</p>
  </>
}
