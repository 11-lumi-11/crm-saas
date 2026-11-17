import { useState, useEffect } from 'react'
import Auth from './Auth'
import { Icono } from './ui'
import { useCrm, salir, setQ } from './store'
import Inicio from './views/Inicio'
import Clientes from './views/Clientes'
import Oportunidades from './views/Oportunidades'
import Actividades from './views/Actividades'
import Productos from './views/Productos'
import Cotizaciones from './views/Cotizaciones'
import Notificaciones from './views/Notificaciones'
import Usuarios from './views/Usuarios'
import { notificacionesApi } from './notificacionesApi'

const VISTAS = { inicio: Inicio, clientes: Clientes, oportunidades: Oportunidades, actividades: Actividades, productos: Productos, cotizaciones: Cotizaciones, notificaciones: Notificaciones, usuarios: Usuarios }
const TITULOS = { inicio: 'Inicio', clientes: 'Clientes', oportunidades: 'Oportunidades', actividades: 'Actividades', productos: 'Productos', cotizaciones: 'Cotizaciones', notificaciones: 'Notificaciones', usuarios: 'Usuarios' }
const RAIL = ['inicio', 'clientes', 'oportunidades', 'actividades', 'productos', 'cotizaciones', 'notificaciones', 'usuarios']

export default function App() {
  const { s, tenant, aviso, q, esAdmin } = useCrm()
  const [vista, setVista] = useState('inicio'), [tab, setTab] = useState(0)
  const [pop, setPop] = useState(null), [ayuda, setAyuda] = useState(true)
  const [hayAvisos, setHayAvisos] = useState(false)

  useEffect(() => {
    if (!s) { setHayAvisos(false); return }
    let activo = true
    const consultar = async () => {
      try {
        const datos = await notificacionesApi.listar()
        if (activo) setHayAvisos(datos.no_leidas_en_pagina > 0)
      } catch { if (activo) setHayAvisos(false) }
    }
    consultar()
    const intervalo = setInterval(consultar, 60000)
    window.addEventListener('crm:avisos-actualizados', consultar)
    return () => { activo = false; clearInterval(intervalo); window.removeEventListener('crm:avisos-actualizados', consultar) }
  }, [s?.usuario_id, s?.tenant_id])

  useEffect(() => { // efecto onda al hacer clic
    const f = (e) => {
      const el = e.target.closest('.btn,.rail button,.col-card,.tabs button,.flujo,.destaque'); if (!el) return
      const r = el.getBoundingClientRect(), o = document.createElement('span')
      o.className = 'onda'; o.style.left = e.clientX - r.left + 'px'; o.style.top = e.clientY - r.top + 'px'
      el.appendChild(o); setTimeout(() => o.remove(), 650)
    }
    document.addEventListener('click', f); return () => document.removeEventListener('click', f)
  }, [])

  if (!s) return <Auth /> // sin sesión no se ve ninguna otra vista

  const actualizarAvisos = () => window.dispatchEvent(new Event('crm:avisos-actualizados'))
  const ir = (v) => { setVista(v); setTab(0); setPop(null); if (v === 'notificaciones') actualizarAvisos() }
  const Vista = VISTAS[vista]
  const tabs = vista === 'inicio' ? ['Inicio', 'Información general'] : [TITULOS[vista]]

  return (
    <div className="sf">
      <aside className="rail">
        {RAIL.filter((k) => k !== 'usuarios' || esAdmin).map((k) => <button key={k} className={vista === k ? 'on' : ''} onClick={() => ir(k)}>
          <span className="ico"><Icono n={k} />{k === 'notificaciones' && hayAvisos && <em aria-label="Hay avisos sin leer">•</em>}</span>{TITULOS[k]}
        </button>)}
      </aside>
      <div className="sf-col">
        <div className="promo"><span><b>{tenant.nombre}</b>: los indicadores de Inicio muestran datos de demostración.</span><button className="btn" onClick={() => ir('inicio')}>Ver flujos</button><div className="rol">Tu rol: <b>{s.rol}</b></div></div>
        <header className="sf-top">
          <div className="logo"><svg width="44" height="44" viewBox="0 0 24 24"><path fill="var(--or)" d="M7.5 19a4.5 4.5 0 0 1-.9-8.9A6 6 0 0 1 18 9a5 5 0 0 1-.5 10z" /></svg>Nodo<b>CRM</b></div>
          <div className="sf-search"><Icono n="buscar" s={20} /><input placeholder="Buscar clientes…" value={q} onChange={(e) => { setQ(e.target.value); ir('clientes') }} />
            <button className="preg" onClick={() => setPop(pop === 'ask' ? null : 'ask')}>✦ Preguntar</button>
            {pop === 'ask' && <div className="pop"><small>¿Qué quieres hacer?</small>
              <button onClick={() => ir('clientes')}>Registrar un cliente</button><button onClick={() => ir('oportunidades')}>Ver mi pipeline de ventas</button><button onClick={() => ir('actividades')}>Ver mis tareas pendientes</button></div>}
          </div>
          <div className="sf-icons">
            <button onClick={() => setAyuda(!ayuda)} aria-label="Ayuda">?</button>
            {esAdmin && <button onClick={() => ir('usuarios')} aria-label="Usuarios">⚙</button>}
            <button onClick={() => ir('notificaciones')} aria-label="Notificaciones"><Icono n="notificaciones" s={24} />{hayAvisos && <span className="badge" aria-label="Hay avisos sin leer">•</span>}</button>
            <button className="avatar" onClick={() => setPop(pop === 'user' ? null : 'user')} aria-label="Cuenta">{s.nombre[0]}</button>
          </div>
          {pop === 'user' && <div className="pop"><b>{s.nombre}</b><small>{tenant.nombre} · {s.rol}</small><button onClick={salir}>Cerrar sesión</button></div>}
          {ayuda && <div className="ayuda"><button className="x" onClick={() => setAyuda(false)} aria-label="Cerrar">✕</button><b>Vuelva siempre que quiera</b><p>Haz clic en el icono ? para obtener ayuda siempre que la necesites.</p></div>}
        </header>
        {pop && <div className="cierra" onClick={() => setPop(null)} />}
        <div className="sf-head"><h1>{TITULOS[vista]}</h1><nav>{tabs.map((t, n) => <button key={t} className={tab === n ? 'on' : ''} onClick={() => setTab(n)}>{t}</button>)}</nav></div>
        <main key={vista}><Vista tab={tab} ir={ir} onCambioNotificaciones={actualizarAvisos} /></main>
        <div className="todo"><button onClick={() => ir('actividades')}><Icono n="lista" s={20} />Ver actividades</button></div>
      </div>
      {aviso && <div className="toast">✓ {aviso}</div>}
    </div>
  )
}
