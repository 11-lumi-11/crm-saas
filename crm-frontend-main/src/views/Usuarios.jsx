import { BotonActualizar } from '../ui'
import { useCacheVista, invalidarVistas } from '../cacheVistas'
import { useEffect, useState } from 'react'
import { listarUsuariosApi, modificarUsuarioApi } from '../authApi'
import { Cabecera, Insignia } from '../ui'

const POR_PAGINA = 6

export default function Usuarios({ activa }) {
  const [usuarios, setUsuarios] = useState([])
  const [siguiente, setSiguiente] = useState(null)
  const [cargandoMas, setCargandoMas] = useState(false)
  const [errorMas, setErrorMas] = useState('')
  const [pagina, setPagina] = useState(0)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [actualizando, setActualizando] = useState({})
  const [erroresUsuario, setErroresUsuario] = useState({})

  const cargarUsuarios = async () => {
    const carga = cache.iniciarCarga()
    if (!cache.estado.current.cargada) setCargando(true); setError('')
    try { const datos = await listarUsuariosApi(); if (!cache.esActual(carga)) return; setUsuarios(datos.usuarios); setSiguiente(datos.siguiente); setPagina(0); setErrorMas(''); cache.registrarCarga(carga) }
    catch (e) { setError(e.message || 'No se pudo cargar la lista de usuarios.') }
    finally { setCargando(false) }
  }
  const cache = useCacheVista('usuarios', activa, cargarUsuarios)

  const cargarMas = async () => {
    setCargandoMas(true); setErrorMas('')
    try {
      const datos = await listarUsuariosApi(siguiente)
      setUsuarios(actuales => [...actuales, ...datos.usuarios]); setSiguiente(datos.siguiente)
    } catch (e) { setErrorMas(e.message || 'No se pudieron cargar más usuarios.') }
    finally { setCargandoMas(false) }
  }

  const totalPaginas = Math.max(1, Math.ceil(usuarios.length / POR_PAGINA))
  const paginaActual = Math.min(pagina, totalPaginas - 1)
  const visibles = usuarios.slice(paginaActual * POR_PAGINA, (paginaActual + 1) * POR_PAGINA)
  const fecha = (valor) => {
    if (!valor) return '—'
    const parsed = new Date(valor)
    return Number.isNaN(parsed.getTime()) ? valor : parsed.toLocaleDateString('es-PE', { day: '2-digit', month: 'short', year: 'numeric' })
  }
  const actualizarUsuario = async (usuario, cambios) => {
    const id = usuario.usuario_id
    if (!id) return
    setActualizando((actuales) => ({ ...actuales, [id]: true }))
    setErroresUsuario((actuales) => ({ ...actuales, [id]: '' }))
    try {
      await modificarUsuarioApi(id, cambios)
      setUsuarios((lista) => lista.map((u) => u.usuario_id === id ? { ...u, ...cambios } : u))
    } catch (e) {
      setErroresUsuario((actuales) => ({ ...actuales, [id]: e.message || 'No se pudo actualizar el usuario.' }))
    } finally {
      setActualizando((actuales) => ({ ...actuales, [id]: false }))
    }
  }

  return <>
    <Cabecera t="Usuarios" sub="Equipo y roles de tu empresa">
      <BotonActualizar onActualizar={cargarUsuarios} disabled={cargando} />
    </Cabecera>

    {error && <div className="error" role="alert">{error}</div>}
    {cargando ? <div className="vacio usuarios-estado">Cargando usuarios…</div> : usuarios.length === 0 ?
      <div className="vacio usuarios-estado">La API todavía no devuelve usuarios.</div> : <>
        <div className="usuarios-resumen">{usuarios.length} {usuarios.length === 1 ? 'usuario cargado' : 'usuarios cargados'}</div>
        <div className="usuarios-grid">
          {visibles.map((u, indice) => <article className="usuario-card" key={u.usuario_id || u.id || u.correo || `${paginaActual}-${indice}`} style={{ '--entrada': `${indice * 65}ms` }}>
            <div className="usuario-card-top"><span className="usuario-avatar">{(u.nombre || '?').trim().charAt(0).toUpperCase()}</span><Insignia v={u.estado || 'sin estado'} /></div>
            <h3>{u.nombre || 'Sin nombre'}</h3>
            <a href={`mailto:${u.correo}`} className="usuario-correo">{u.correo || 'Sin correo'}</a>
            <div className="usuario-meta"><span>ID</span><b>{u.usuario_id || '—'}</b></div>
            <div className="usuario-meta"><span>Rol</span><b>{u.rol || 'Sin rol'}</b></div>
            <div className="usuario-meta"><span>Creado</span><b>{fecha(u.fecha_creacion)}</b></div>
            <label className="usuario-control">Cambiar rol
              <select value={['vendedor', 'gerente', 'admin'].includes(u.rol) ? u.rol : 'vendedor'} disabled={actualizando[u.usuario_id] || !u.usuario_id}
                onChange={(e) => actualizarUsuario(u, { rol: e.target.value })}>
                {['vendedor', 'gerente', 'admin'].map((rol) => <option key={rol} value={rol}>{rol}</option>)}
              </select>
            </label>
            <div className="usuario-control"><span>Estado</span>
              <button type="button" className={`estado-switch ${String(u.estado).toLowerCase() === 'activo' ? 'activo' : 'inactivo'}`}
                aria-pressed={String(u.estado).toLowerCase() === 'activo'} disabled={actualizando[u.usuario_id] || !u.usuario_id}
                onClick={() => actualizarUsuario(u, { estado: String(u.estado).toLowerCase() === 'activo' ? 'inactivo' : 'activo' })}>
                <i aria-hidden="true" /><b>{String(u.estado).toLowerCase() === 'activo' ? 'Activo' : 'Inactivo'}</b>
              </button>
            </div>
            {erroresUsuario[u.usuario_id] && <p className="usuario-error" role="alert">{erroresUsuario[u.usuario_id]}</p>}
          </article>)}
        </div>
        <nav className="usuarios-paginacion" aria-label="Paginación de usuarios">
          <button className="btn" onClick={() => setPagina((p) => Math.max(0, p - 1))} disabled={paginaActual === 0}>Anterior</button>
          <span>Página {paginaActual + 1} de {totalPaginas}</span>
          <button className="btn" onClick={() => setPagina((p) => Math.min(totalPaginas - 1, p + 1))} disabled={paginaActual >= totalPaginas - 1}>Siguiente</button>
        </nav>
        {errorMas && <p className="error" role="alert">{errorMas}</p>}
        {siguiente && <button className="btn" disabled={cargandoMas} onClick={cargarMas}>{cargandoMas ? 'Cargando…' : 'Cargar más usuarios'}</button>}
      </>}


  </>
}
