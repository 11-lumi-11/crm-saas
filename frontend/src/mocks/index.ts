import type { Actividad, Cliente, Contacto, Notificacion, Oportunidad } from '../types'

export const clientesMock: Cliente[] = [
  { cliente_id: 'cli_000123', nombre: 'Constructora Andes', tipo: 'empresa', documento: '20123456789', correo: 'compras@andes.pe', telefono: '999 111 222', industria: 'Construcción', ciudad: 'Lima', estado: 'activo', responsable_id: 'usr_demo', fecha_creacion: '2026-10-19T10:00:00Z' },
  { cliente_id: 'cli_000124', nombre: 'Grupo Pacífico', tipo: 'empresa', documento: '20567891234', correo: 'hola@pacifico.pe', telefono: '987 225 440', industria: 'Seguros', ciudad: 'Arequipa', estado: 'prospecto', responsable_id: 'usr_demo', fecha_creacion: '2026-11-02T10:00:00Z' },
  { cliente_id: 'cli_000125', nombre: 'Mariana Torres', tipo: 'persona', documento: '45891236', correo: 'mariana@torres.pe', telefono: '955 043 901', industria: 'Consultoría', ciudad: 'Lima', estado: 'activo', responsable_id: 'usr_demo', fecha_creacion: '2026-11-08T10:00:00Z' },
]
export const contactosMock: Contacto[] = [{ contacto_id: 'con_000456', cliente_id: 'cli_000123', nombre: 'Ana Rodríguez', cargo: 'Gerente de compras', correo: 'ana@andes.pe', telefono: '988 777 666', es_principal: true, fecha_creacion: '2026-10-19T10:00:00Z' }]
export const oportunidadesMock: Oportunidad[] = [
  { oportunidad_id: 'opo_000045', cliente_id: 'cli_000123', cliente_nombre: 'Constructora Andes', titulo: 'Seguro de flota', monto_estimado: 80000, moneda: 'PEN', etapa: 'en_negociacion', probabilidad: 75, responsable_id: 'usr_demo', fecha_creacion: '2026-11-09T10:00:00Z' },
  { oportunidad_id: 'opo_000046', cliente_id: 'cli_000124', cliente_nombre: 'Grupo Pacífico', titulo: 'Plan corporativo anual', monto_estimado: 12000, moneda: 'USD', etapa: 'propuesta', probabilidad: 50, responsable_id: 'usr_demo', fecha_creacion: '2026-11-06T10:00:00Z' },
  { oportunidad_id: 'opo_000047', cliente_id: 'cli_000125', cliente_nombre: 'Mariana Torres', titulo: 'Consultoría de riesgos', monto_estimado: 25000, moneda: 'PEN', etapa: 'calificada', probabilidad: 25, responsable_id: 'usr_demo', fecha_creacion: '2026-11-10T10:00:00Z' },
]
export const actividadesMock: Actividad[] = [{ actividad_id: 'act_1', tipo: 'llamada', titulo: 'Seguimiento a propuesta', fecha_programada: '2026-11-12T14:00:00Z', estado: 'pendiente', responsable_id: 'usr_demo' }]
export const notificacionesMock: Notificacion[] = [{ notificacion_id: 'not_1', tipo: 'oportunidad.etapa_cambiada', titulo: 'Oportunidad actualizada', mensaje: 'Seguro de flota avanzó a negociación.', leida: false, fecha_creacion: '2026-11-11T11:20:00Z' }]
