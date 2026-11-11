import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs))

export const dinero = (monto: number | string, moneda = 'PEN') => new Intl.NumberFormat('es-PE', {
  style: 'currency', currency: moneda, currencyDisplay: 'narrowSymbol', maximumFractionDigits: 0,
}).format(Number(monto))

export const fecha = (valor?: string) => valor ? new Intl.DateTimeFormat('es-PE', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(valor)) : '—'

export const iniciales = (nombre = '') => nombre.split(' ').filter(Boolean).slice(0, 2).map((palabra) => palabra[0]).join('').toUpperCase() || 'VC'
