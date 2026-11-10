import json

from src.utilidades import ErrorNegocio, cambiar_etapa

# Errores que no tiene sentido reintentar: SQS entrega al menos una vez (idempotencia)
OMITIR = ('no_encontrado', 'oportunidad_cerrada')


def lambda_handler(event, context):
    fallidos = []

    for registro in event.get('Records', []):
        mensaje_id = registro['messageId']
        try:
            sobre = json.loads(registro['body'])      # sobre de SNS
            evento = json.loads(sobre['Message'])      # evento real
            tenant_id = evento['tenant_id']            # el tenant sale del evento
            oportunidad_id = evento['datos']['oportunidad_id']

            cambiar_etapa(tenant_id, oportunidad_id, 'ganada', None, 'sistema')
            print(f"Oportunidad {oportunidad_id} ({tenant_id}) marcada como ganada por cotización aceptada")
        except ErrorNegocio as e:
            if e.codigo in OMITIR:
                print(f"Mensaje {mensaje_id} omitido ({e.codigo}): {e.mensaje}")
            else:
                # conflicto_etapa u otro: reintentar
                print(f"Mensaje {mensaje_id} fallido ({e.codigo}): {e.mensaje}")
                fallidos.append({'itemIdentifier': mensaje_id})
        except Exception as e:
            print(f"Error inesperado en mensaje {mensaje_id}: {e}")
            fallidos.append({'itemIdentifier': mensaje_id})

    # Esta cadena termina aquí: no se publica ningún otro evento (aparte de oportunidad.ganada de cambiar_etapa)
    return {'batchItemFailures': fallidos}
