import { useEffect, useRef, useState } from 'react'
import { notificacionesApi } from '../notificacionesApi'
import { dia } from '../store'
import { Cabecera } from '../ui'

export default function Notificaciones({ onCambioNotificaciones }) {
  const [avisos, setAvisos] = useState([])
  const [siguiente, setSiguiente] = useState(null)
  const [soloNoLeidas, setSoloNoLeidas] = useState(false)
  const [cargando, setCargando] = useState(true)
  const [cargandoMas, setCargandoMas] = useState(false)
  const [marcando, setMarcando] = useState(null)
  const [error, setError] = useState('')
  const version = useRef(0)

  const cargar = async () => {
    const actual = ++version.current
    setCargando(true); setError('')
    try {
      const datos = await notificacionesApi.listar({ soloNoLeidas })
      if (actual !== version.current) return
      setAvisos(datos.notificaciones); setSiguiente(datos.siguiente)
    } catch (e) {
      if (actual === version.current) setError(e.message || 'No se pudieron cargar las notificaciones.')
    } finally {
      if (actual === version.current) setCargando(false)
    }
  }
  useEffect(() => {
    cargar()
    return () => { version.current++ }
  }, [soloNoLeidas])

  const mas = async () => {
    const actual = version.current
    setCargandoMas(true); setError('')
    try {
      const datos = await notificacionesApi.listar({ siguiente, soloNoLeidas })
      if (actual !== version.current) return
      setAvisos(prev => [...prev, ...datos.notificaciones]); setSiguiente(datos.siguiente)
    } catch (e) {
      if (actual === version.current) setError(e.message || 'No se pudieron cargar más notificaciones.')
    } finally { setCargandoMas(false) }
  }
  const leer = async id => {
    const actual = version.current
    setMarcando(id); setError('')
    try {
      await notificacionesApi.marcarLeida(id)
      if (actual === version.current) setAvisos(prev => soloNoLeidas ? prev.filter(n => n.notificacion_id !== id)
        : prev.map(n => n.notificacion_id === id ? { ...n, leida: true } : n))
      onCambioNotificaciones?.()
    } catch (e) { if (actual === version.current) setError(e.message || 'No se pudo marcar el aviso como leído.') }
    finally { setMarcando(null) }
  }

  return <>
    <Cabecera t="Notificaciones" sub="Avisos dirigidos a ti o a tu rol">
      <button className="btn" onClick={cargar} disabled={cargando}>↻ Actualizar</button>
    </Cabecera>
    <p className="nota">Los avisos por eventos pueden tardar unos minutos. Usa Actualizar para volver a consultarlos.</p>
    <label><input type="checkbox" checked={soloNoLeidas} onChange={e => setSoloNoLeidas(e.target.checked)} /> Solo no leídas</label>
    {error && <div className="error" role="alert">{error}</div>}
    {cargando ? <div className="vacio">Cargando notificaciones…</div> : <>
      {avisos.length ? avisos.map(n => <div className={`aviso ${n.leida ? '' : 'nuevo'}`} key={n.notificacion_id}>
        <div><b>{n.titulo}</b><p>{n.mensaje}</p><small>{n.tipo} · {dia(n.fecha_creacion)}</small></div>
        {!n.leida && <button className="btn mini" disabled={Boolean(marcando)} onClick={() => leer(n.notificacion_id)}>{marcando === n.notificacion_id ? 'Guardando…' : 'Marcar leída'}</button>}
      </div>) : <div className="vacio">No hay avisos en esta página.</div>}
      {siguiente && <button className="btn" disabled={cargandoMas} onClick={mas}>{cargandoMas ? 'Cargando…' : 'Cargar más notificaciones'}</button>}
    </>}
  </>
}
