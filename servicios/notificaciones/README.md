# Notificaciones

Escucha los eventos del topic SNS compartido mediante su cola SQS (con DLQ) y guarda avisos en `t_notificaciones`. La lectura es individual por usuario (`t_lecturas_notificaciones`).

- `GET /notificaciones` (protegido): avisos del usuario y de su rol, más recientes primero. Parámetros: `limite` (1-100), `solo_no_leidas=true`, `siguiente` (cursor de la respuesta anterior).
- `PUT /notificaciones/{notificacion_id}/leer` (protegido): marca el aviso como leído para el usuario del token. Idempotente.

Desplegar después de `compartido` y antes de generar eventos de prueba:

    serverless deploy --stage dev
