# Validación y preparación del entorno

Revisión: 2026-11-11. No se desplegó ni se ejecutó la migración en AWS durante esta revisión.

## Pruebas locales

Desde la raíz, con Python 3.14:

La validación se ejecutó localmente con un entorno virtual de Python 3.14, dependencias de desarrollo y la suite privada de pruebas del trabajo. Esos archivos de prueba y dependencias locales no forman parte del commit.

La suite privada cubrió contratos HTTP, PBKDF2 y migración de SHA-256, estado/rol del Authorizer, altas atómicas, conflictos condicionales, protección de administradores, principal de contacto, archivo, outbox, consumo SQS e importación de todos los handlers. Usó boto3 simulado y credenciales ficticias; no contactó AWS. Las pruebas de infraestructura leyeron YAML con etiquetas CloudFormation y resolvieron los módulos; no sustituyen `serverless package`, CloudFormation ni pruebas de permisos.

Resultado de esta revisión: **28 pruebas pasan**, compilación sin errores y análisis estático sin hallazgos con pyflakes. No se midió rendimiento de PBKDF2 en Lambda.

## Preparación de despliegue

Requisitos: AWS Academy activa con LabRole, Serverless Framework 4, Python 3.14 y `JWT_SECRET` configurado en el entorno de despliegue. El framework usa credenciales locales; no se deben registrar en documentos ni subir al repositorio. La región actual es `us-east-1`.

Preparar la capa PyJWT desde la raíz:

```sh
.venv/bin/pip install -r compartido/capa_jwt/requirements.txt --target compartido/capa_jwt/python
```

La capa `compartido/capa_comun/python/crm_comun` ya contiene los módulos propios. boto3 se proporciona mediante el runtime de Lambda; las dependencias de desarrollo no se empaquetan en los servicios.

Cada carpeta contiene su stack; ejecutar `serverless deploy --stage dev` dentro de cada una, en este orden:

1. `compartido`.
2. `servicios/usuarios`.
3. `servicios/clientes`.
4. `servicios/oportunidades`.

Usar el mismo stage en todos. Si cambia una capa, desplegar nuevamente los servicios dependientes para tomar su nuevo ARN/version. No retirar stacks de otros integrantes. El Authorizer rechazará accesos hasta que existan usuario y tenant activos en las tablas del stage.

Antes de dar el despliegue por validado, comprobar que LabRole permite lecturas y transacciones DynamoDB, publicación SNS, consumo SQS, funciones programadas y concurrencia reservada del publicador. El nuevo GSI de Clientes necesita completar su construcción. Registrar ejecución y resultados en la matriz AWS del documento base.

## Migrar una instalación existente

La migración prepara los candados de correos y la referencia al contacto principal, usando los registros actuales. No genera los datos ficticios ni cambia contraseñas. Los hashes previos migran durante un login correcto.

**Mantener pausadas las escrituras desde antes del despliegue hasta finalizar la migración.** Pausar el tráfico de las APIs en el entorno que actualiza el grupo; el repositorio no automatiza esa pausa. Evitar accesos concurrentes al script. Si no se puede garantizar la pausa, usar primero un entorno nuevo.

Con las tablas nuevas ya desplegadas, ejecutar primero la auditoría (solo lectura):

```sh
.venv/bin/python datos/migrar_integridad.py --stage dev
```

Si no hay inconsistencias, aplicar:

```sh
.venv/bin/python datos/migrar_integridad.py --stage dev --aplicar
```

El script recorre todas las páginas con lectura consistente, detecta correos duplicados, múltiples principales, contactos principales huérfanos y candados inconsistentes. Audita antes de escribir y se puede repetir: permite candados que ya pertenecen al mismo usuario y referencias al mismo contacto. Si una escritura falla a mitad de aplicación, mantener la pausa, corregir la causa y repetir; no se trata de una sola transacción global. No elige ni elimina duplicados automáticamente. Si informa inconsistencias, resolverlas con el grupo antes de habilitar las escrituras.

Conservar el resultado sin datos personales y completar las pruebas de registro, creación de principales, login, permisos y archivo antes de reabrir el entorno.

## Eventos y verificación funcional

Los eventos de Usuarios, Clientes y Oportunidades se guardan en sus tablas `dev-t_eventos_<servicio>` dentro de la transacción de negocio. Cada publicador corre una vez por minuto, envía los pendientes a SNS y marca enviados con TTL de siete días. Los pendientes no expiran. No hay publicación inmediata ni garantía de orden global. Un fallo tras publicar y antes de marcar puede duplicar el mismo `evento_id`; el consumidor debe ser idempotente.

La función `publicarEventos` también se puede invocar manualmente en un entorno de prueba para evitar esperar el intervalo. Revisar logs y pendientes si no llegan avisos. Verificar SNS → SQS → consumidor por separado, incluyendo atributo `tipo`, sobre SNS, errores parciales y DLQ tras tres intentos.

La colección Postman utiliza URLs por servicio: actualizar sus variables tras desplegar. Los DELETE mantienen respuesta 200 e identificador, pero ahora archivan y conservan contactos/historial. Ninguna ejecución de Postman ni de publicación manual en AWS se ha acreditado en esta revisión.

Los escenarios completos y la tabla para registrar evidencia están en [documento_base.md, sección 14](documento_base.md#14-validación-pendientes-y-evidencia-aws).
