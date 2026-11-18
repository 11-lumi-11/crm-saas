import { useState } from 'react'
import { txt } from './store'

export const Insignia = ({ v }) => <span className={`ins ins-${v}`}>{txt(v)}</span>

export function Modal({ titulo, onClose, ancho, children }) {
  return (
    <div className="velo" onMouseDown={onClose}>
      <div className="modal" style={{ maxWidth: ancho || 520 }} onMouseDown={(e) => e.stopPropagation()}>
        <header><h3>{titulo}</h3><button className="x" onClick={onClose} aria-label="Cerrar">✕</button></header>
        {children}
      </div>
    </div>
  )
}

/* f = [{k, l, t?, o?, d?, r?}]  k=campo, l=etiqueta, t=tipo, o=opciones, d=valor inicial, r=false → opcional */
export function Form({ f, onSubmit, ok = 'Guardar', disabled = false }) {
  const ini = (x) => x.d ?? (x.o ? (Array.isArray(x.o[0]) ? x.o[0][0] : x.o[0]) : '')
  const [v, setV] = useState(() => Object.fromEntries(f.map((x) => [x.k, ini(x)])))
  const set = (k, val) => setV((p) => ({ ...p, [k]: val }))
  return (
    <form className="form" onSubmit={(e) => { e.preventDefault(); if (!disabled) onSubmit(v) }}>
      {f.map((x) => (
        <label key={x.k}>{x.l}
          {x.o ? (
            <select value={v[x.k]} onChange={(e) => set(x.k, e.target.value)}>
              {x.o.map((o) => { const [a, c] = Array.isArray(o) ? o : [o, txt(o)]; return <option key={a} value={a}>{c}</option> })}
            </select>
          ) : (
            <input type={x.t || 'text'} required={x.r !== false} value={v[x.k]} onChange={(e) => set(x.k, e.target.value)} />
          )}
        </label>
      ))}
      <button className="btn pri" disabled={disabled}>{ok}</button>
    </form>
  )
}

export const Tabla = ({ cols, rows, onRow, vacio }) =>
  rows.length ? (
    <div className="tabla-wrap"><table>
      <thead><tr>{cols.map((c) => <th key={c[0]}>{c[0]}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i} className={onRow ? 'clic' : ''} onClick={() => onRow?.(r)}>{cols.map((c) => <td key={c[0]}>{c[1](r)}</td>)}</tr>)}</tbody>
    </table></div>
  ) : <div className="vacio">{vacio}</div>

export const Cabecera = ({ t, sub, children }) => (
  <div className="cab"><p>{sub}</p><div>{children}</div></div>
)

// Mantiene el contenido visible y confirma que la consulta está en curso.
export function BotonActualizar({ onActualizar, disabled = false }) {
  const [actualizando, setActualizando] = useState(false)
  const actualizar = async () => {
    setActualizando(true)
    const inicio = Date.now()
    try { await onActualizar() }
    finally {
      const restante = Math.max(0, 450 - (Date.now() - inicio))
      if (restante) await new Promise(resolve => setTimeout(resolve, restante))
      setActualizando(false)
    }
  }
  return <span className="actualizar-control">
    <button type="button" className="btn" onClick={actualizar} disabled={disabled || actualizando}>
      <span className={actualizando ? 'actualizar-icono girando' : 'actualizar-icono'} aria-hidden="true">↻</span>{' '}
      {actualizando ? 'Actualizando…' : 'Actualizar'}
    </button>
    {actualizando && <span className="actualizar-skeleton" aria-hidden="true" />}
    <span className="actualizar-estado" role="status">{actualizando ? 'Actualizando datos' : ''}</span>
  </span>
}

const P = {
  inicio: 'M3 11l9-8 9 8v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z',
  clientes: 'M16 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2 20c0-3 3-5 6-5s6 2 6 5M14 15c3 0 8 1 8 5',
  oportunidades: 'M3 3v18h18M7 15l4-4 3 3 5-6',
  actividades: 'M9 6h12M9 12h12M9 18h12M3 6l1 1 2-2M3 12l1 1 2-2M3 18l1 1 2-2',
  productos: 'M21 8l-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8',
  cotizaciones: 'M6 2h9l5 5v15H6zM14 2v6h6M9 13h8M9 17h8',
  notificaciones: 'M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10 21a2 2 0 0 0 4 0',
  usuarios: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-4 4-6 8-6s8 2 8 6',
  buscar: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3',
  lista: 'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
  video: 'M3 7h12v10H3zM15 11l6-3v8l-6-3',
}
export const Icono = ({ n, s = 28 }) => <svg className="svg" width={s} height={s} viewBox="0 0 24 24"><path d={P[n]} /></svg>
