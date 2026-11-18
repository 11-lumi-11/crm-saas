import { BotonActualizar } from '../ui'
import { useCacheVista, invalidarVistas } from '../cacheVistas'
import { useState, useEffect } from 'react'
import { useCrm, ETAPAS, txt, dia } from '../store'
import { clientesApi } from '../clientesApi'
import { oportunidadesApi, actividadesApi } from '../apiComercial'
import { Icono, Form, Modal } from '../ui'
import { crearUsuarioApi } from '../authApi'

const SLIDES = [
  ['Bienvenido a NodoCRM', 'Ventas, clientes y cotizaciones de tu empresa en un solo lugar.'],
  ['Clientes y contactos', 'Registra cuentas y a las personas con las que hablas.'],
  ['Pipeline de ventas', 'La cotización enviada inicia la negociación y su aceptación confirma la venta.'],
  ['Actividades y avisos', 'Los seguimientos se crean al enviar cotizaciones.'],
  ['Cotizaciones', 'La aceptación se confirma cuando la oportunidad puede marcarse como ganada.'],
]
const FLUJOS = [
  ['clientes', 'clientes', 'Clientes: registrar su primer cliente', 'Crea una cuenta y agrega su contacto principal', '#d9f2e4', '#1f8a5b'],
  ['oportunidades', 'oportunidades', 'Oportunidades: cerrar la primera negociación', 'Envía y acepta una cotización para concretar la venta', '#d4ecff', '#0b5cd5'],
  ['cotizaciones', 'cotizaciones', 'Cotizaciones: enviar su primera oferta', 'Arma una cotización con productos del catálogo', '#fde3ec', '#a8164b'],
  ['actividades', 'actividades', 'Actividades: completar un seguimiento', 'Marca una llamada o tarea como completada', '#fff0d1', '#946100'],
]

export default function Inicio({ tab, ir, activa }) {
  const { s, esAdmin, esVend } = useCrm()
  const [i, setI] = useState(0), [play, setPlay] = useState(false)
  const [resumen, setResumen] = useState(null)
  const [cargandoResumen, setCargandoResumen] = useState(false)
  const [errorResumen, setErrorResumen] = useState('')
  const [mostrarCrearUsuario, setMostrarCrearUsuario] = useState(false)
  const [guardandoUsuario, setGuardandoUsuario] = useState(false)
  const [mensajeUsuario, setMensajeUsuario] = useState('')
  const [errorUsuario, setErrorUsuario] = useState('')
  const crearUsuario = async (datos) => {
    setGuardandoUsuario(true); setErrorUsuario(''); setMensajeUsuario('')
    try {
      await crearUsuarioApi(datos)
      invalidarVistas('usuarios', 'notificaciones')
      setMensajeUsuario('Usuario creado correctamente.')
      setMostrarCrearUsuario(false)
    } catch (error) {
      setErrorUsuario(error.message || 'No se pudo crear el usuario.')
    } finally { setGuardandoUsuario(false) }
  }
  useEffect(() => {
    if (!play) return
    const t = setInterval(() => setI((x) => (x + 1) % SLIDES.length), 3000)
    return () => clearInterval(t)
  }, [play])

  const cargarResumen = async () => {
    const carga = cache.iniciarCarga()
    if (!cache.estado.current.cargada) setCargandoResumen(true)
    setErrorResumen('')
    try {
      const [clientes, oportunidades, actividades] = await Promise.all([
        clientesApi.listar(), oportunidadesApi.listar(),
        actividadesApi.listar(esVend ? { responsable_id: s.usuario_id } : {}),
      ])
      if (!cache.esActual(carga)) return
      setResumen({ clientes, oportunidades, actividades }); cache.registrarCarga(carga)
    } catch (error) { setErrorResumen(error.message || 'No se pudo cargar la información general.') }
    finally { setCargandoResumen(false) }
  }
  const cache = useCacheVista('inicio', activa && tab === 1, cargarResumen)


  if (tab === 1) {
    if (cargandoResumen || (!resumen && !errorResumen)) return <div className="vacio">Cargando información general…</div>
    if (errorResumen && !resumen) return <div className="error" role="alert">{errorResumen} <button className="btn mini" onClick={cargarResumen}>Reintentar</button></div>
    const oportunidades = resumen.oportunidades.oportunidades
    const ab = oportunidades.filter((o) => !['ganada', 'perdida'].includes(o.etapa))
    const kpi = [['Clientes cargados', resumen.clientes.clientes.length], ['Oportunidades abiertas', ab.length], ['Oportunidades ganadas', oportunidades.filter((o) => o.etapa === 'ganada').length]]
    const max = Math.max(1, ...ETAPAS.map((e) => oportunidades.filter((o) => o.etapa === e).length))
    const pend = resumen.actividades.actividades.filter((a) => a.estado === 'pendiente')
    return <>
      <BotonActualizar onActualizar={cargarResumen} disabled={cargandoResumen} />
      {errorResumen && <div className="error" role="alert">{errorResumen} <button className="btn mini" onClick={cargarResumen}>Reintentar</button></div>}
      <p className="nota">Resumen de la primera página de cada lista. Los indicadores pueden no incluir todos los registros; consulta cada sección para cargar más.</p>
      <div className="kpis">{kpi.map(([l, v]) => <div className="kpi" key={l}><span>{l}</span><strong>{v}</strong></div>)}</div>
      <div className="dos">
        <section className="panel"><h3>Embudo de ventas</h3>
          {ETAPAS.map((e) => { const n = oportunidades.filter((o) => o.etapa === e).length; return <div className="barra" key={e}><span>{txt(e)}</span><i style={{ width: `${(n / max) * 100}%` }} className={`b-${e}`} /><b>{n}</b></div> })}
        </section>
        <section className="panel"><h3>Actividades pendientes cargadas</h3>
          {pend.slice(0, 5).map((a) => <div className="fila" key={a.actividad_id}><span>{a.titulo}</span><small>{dia(a.fecha_programada)}</small></div>)}
          {!pend.length && <div className="vacio">No hay tareas pendientes en esta página.</div>}
        </section>
      </div>
    </>
  }

  return <>
    <section className="hero"><h1>Comencemos, <span>{s.nombre.split(' ')[0]}</span></h1><p>Hay mucho por descubrir. Explora NodoCRM en acción.</p></section>
    <div className="dos-cards">
    {esAdmin && <section className="card-sf admin-user-card">
      <h3>Administración de usuarios</h3>
      <p>Agrega a una persona al equipo de tu empresa.</p>
      <button className="btn pri" onClick={() => { setErrorUsuario(''); setMostrarCrearUsuario(true) }}>＋ Crear usuario</button>
      {mensajeUsuario && <p role="status">{mensajeUsuario}</p>}
      {errorUsuario && <p className="error" role="alert">{errorUsuario}</p>}
    </section>}
      <section className="card-sf"><h3>Conozca NodoCRM</h3>
        <div className="tour">
          <div className="tour-in"><div className="slide" key={i}><h4>{SLIDES[i][0]}</h4><p>{SLIDES[i][1]}</p></div></div>
          <div className="tour-bar"><span>{i + 1}/{SLIDES.length}</span>
            <div><button onClick={() => setI((i + SLIDES.length - 1) % SLIDES.length)} aria-label="Anterior">←</button><button onClick={() => setPlay(!play)} aria-label="Reproducir">{play ? '❚❚' : '▶'}</button><button onClick={() => setI((i + 1) % SLIDES.length)} aria-label="Siguiente">→</button></div></div>
        </div>
        <button className="destaque" onClick={() => { setI(0); setPlay(true) }}><span><Icono n="video" s={22} /></span><div><b>Haga una visita guiada a su CRM</b><small>Repasa los módulos y cómo se conectan entre sí</small></div></button>
      </section>
      <section className="card-sf"><h3>Flujos de trabajo guiados</h3>
        <div className="prev"><i /><i /><div className="burbuja">👋 Te mostraremos cómo realizar tu trabajo.</div></div>
        {FLUJOS.map(([v, ic, t, d, bg, fg]) => <button className="flujo" key={v} onClick={() => ir(v)}>
          <span className="ic" style={{ background: bg, color: fg }}><Icono n={ic} s={22} /></span><div><b>{t}</b><small>{d}</small></div><span className="flecha">→</span>
        </button>)}
      </section>
    </div>
    {mostrarCrearUsuario && <Modal titulo="Crear usuario" onClose={() => !guardandoUsuario && setMostrarCrearUsuario(false)}>
      <Form disabled={guardandoUsuario} ok={guardandoUsuario ? 'Creando…' : 'Crear usuario'} onSubmit={crearUsuario}
        f={[{ k: 'nombre', l: 'Nombre completo' }, { k: 'correo', l: 'Correo', t: 'email' }, { k: 'contrasena', l: 'Contraseña', t: 'password' }, { k: 'rol', l: 'Rol', o: ['vendedor', 'gerente', 'admin'] }]} />
      {errorUsuario && <div className="error" role="alert">{errorUsuario}</div>}
    </Modal>}
  </>
}
