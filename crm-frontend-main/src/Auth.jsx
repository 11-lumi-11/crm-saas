import { useState } from 'react'
import { Form } from './ui'
import { login, registro } from './store'

export default function Auth() {
  const [m, setM] = useState('login')
  const [err, setErr] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [enviando, setEnviando] = useState(false)
  const go = async (v) => {
    setErr(''); setMensaje(''); setEnviando(true)
    try {
      const error = await (m === 'login' ? login(v) : registro(v))
      if (error) setErr(error)
      else if (m === 'reg') {
        setM('login')
        setMensaje('Empresa creada. Inicia sesión con tu correo y contraseña.')
      }
    }
    finally { setEnviando(false) }
  }
  const cambiar = (x) => { setM(x); setErr(''); setMensaje('') }
  return (
    <div className="auth">
      <div className="forma" />
      <section className="auth-info">
        <div className="logo">Nodo<b>CRM</b></div>
        <h1>El CRM que crece con tu empresa</h1>
        <p>Clientes, oportunidades, tareas y cotizaciones en un solo lugar. Cada empresa ve solo sus propios datos.</p>
        <ul><li>Pipeline visual de ventas</li><li>Avisos automáticos entre equipos</li><li>Acceso por rol: vendedor, gerente y admin</li></ul>
        <div className="auth-preview" aria-hidden="true">
          <div className="preview-head"><span className="preview-dots"><i /><i /><i /></span><b>Pipeline de ventas</b><span className="preview-total">S/ 24.8k</span></div>
          <div className="preview-stages">
            <div className="preview-stage"><span>Contacto</span><article><i className="preview-avatar">LM</i><b>Andes Studio</b><small>Nuevo cliente</small><em /></article><article className="preview-ghost"><i className="preview-avatar">CR</i><b>Costa Norte</b><small>Seguimiento</small><em /></article></div>
            <div className="preview-stage"><span>En negociación</span><article className="preview-deal"><i className="preview-avatar">PV</i><b>Proyecto Verde</b><small>Propuesta enviada</small><em /></article></div>
            <div className="preview-stage"><span>Cerrado</span><article className="preview-won"><i className="preview-avatar">AC</i><b>Alma Café</b><small>Cliente ganado</small><em /></article></div>
          </div>
          <div className="preview-notice"><span>✓</span><div><b>Oportunidad actualizada</b><small>Proyecto Verde · S/ 8,400</small></div></div>
          <div className="preview-orbit preview-orbit-one" /><div className="preview-orbit preview-orbit-two" />
        </div>
      </section>
      <div className="auth-card" key={m}>
        <div className="tabs">
          <button className={m === 'login' ? 'on' : ''} onClick={() => cambiar('login')}>Iniciar sesión</button>
          <button className={m === 'reg' ? 'on' : ''} onClick={() => cambiar('reg')}>Registrar empresa</button>
        </div>
        {err && <div className="error">{err}</div>}
        {mensaje && <p role="status">{mensaje}</p>}
        <Form
          ok={enviando ? 'Conectando…' : m === 'login' ? 'Entrar' : 'Crear empresa'}
          disabled={enviando}
          onSubmit={go}
          f={m === 'login'
            ? [{ k: 'correo', l: 'Correo', t: 'email' }, { k: 'contrasena', l: 'Contraseña', t: 'password' }]
            : [{ k: 'empresa', l: 'Nombre de la empresa' }, { k: 'rubro', l: 'Rubro' }, { k: 'nombre', l: 'Tu nombre completo' }, { k: 'correo', l: 'Correo', t: 'email' }, { k: 'contrasena', l: 'Contraseña', t: 'password' }]}
        />
      </div>
    </div>
  )
}
