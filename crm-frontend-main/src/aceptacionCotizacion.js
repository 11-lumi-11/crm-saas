// Mantiene pendiente la solicitud si el GET todavía refleja una solicitud anterior.
export function aplicarResultadoAceptacion(actual, nuevo) {
  if (actual.estado !== 'aceptacion_pendiente') return actual
  const anterior = actual._solicitudAnterior
  if (anterior !== undefined && nuevo.solicitud_aceptacion_id === anterior) return actual
  if (nuevo.estado === 'aceptacion_pendiente') return { ...nuevo, _solicitudAnterior: anterior }
  if (nuevo.resultado_solicitud_id && nuevo.resultado_solicitud_id === nuevo.solicitud_aceptacion_id) return nuevo
  return actual
}
