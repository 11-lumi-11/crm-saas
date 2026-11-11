export type Rol = 'admin' | 'gerente' | 'vendedor'
export type Etapa = 'nueva' | 'calificada' | 'propuesta' | 'en_negociacion' | 'ganada' | 'perdida'
export type EstadoCliente = 'prospecto' | 'activo' | 'inactivo'

export interface Usuario { usuario_id: string; tenant_id: string; nombre: string; correo: string; rol: Rol; estado: 'activo' | 'inactivo'; fecha_creacion?: string }
export interface Sesion { token: string; usuario_id: string; tenant_id: string; rol: Rol; usuario?: Usuario; tenantNombre?: string }
export interface Cliente {
  cliente_id: string; tenant_id?: string; nombre: string; tipo: 'empresa' | 'persona'; documento?: string; correo?: string; telefono?: string;
  industria?: string; ciudad?: string; estado: EstadoCliente; responsable_id: string; fecha_creacion?: string; fecha_actualizacion?: string;
}
export interface Contacto { contacto_id: string; cliente_id: string; nombre: string; cargo?: string; correo?: string; telefono?: string; es_principal: boolean; fecha_creacion?: string }
export interface Oportunidad { oportunidad_id: string; cliente_id: string; cliente_nombre?: string; titulo: string; monto_estimado: number; moneda: 'PEN' | 'USD'; etapa: Etapa; probabilidad: number; responsable_id: string; fecha_creacion?: string; fecha_cierre_estimada?: string }
export interface Actividad { actividad_id: string; tipo: string; titulo: string; fecha_programada: string; estado: string; responsable_id: string }
export interface Notificacion { notificacion_id: string; tipo: string; titulo: string; mensaje: string; leida: boolean; fecha_creacion: string }
export interface Pagina<T> { items: T[]; siguiente: string | null }
