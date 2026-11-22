# Prueba de Parameter Store y documentos S3

Importa `CRM-SaaS-documentos-s3.postman_collection.json` en Postman. Esta colección complementa las existentes. Usa **No environment** para que otro entorno no sobrescriba sus variables.

En las variables de la colección configura `correo_a`, `contrasena_a` y `cliente_id` con un usuario y un cliente existentes del tenant A; configura `correo_b` y `contrasena_b` con un usuario de otro tenant. Si aún no tienes un cliente, puedes crearlo con la colección principal. No compartas ni subas contraseñas, tokens o el enlace de descarga.

Ejecuta manualmente y en orden:

1. **Login A:** devuelve un token y guarda el tenant. El login desplegado lee su clave de Parameter Store. Si no conoces el ID del cliente, ejecuta después **1b. Listar clientes**, copia un `cliente_id` de la respuesta y colócalo en la variable de la colección.
2. **Consultar cliente A:** comprueba que el token funciona ante el Authorizer y que el cliente existe en ese tenant. El Authorizer también lee la clave de Parameter Store.
3. **Subir documento:** crea `prueba-s3.txt` y guarda el ID devuelto. Cada ejecución de este POST crea un documento real adicional; no hay eliminación en este flujo.
4. **Listar:** busca el documento. El índice de DynamoDB puede tardar unos segundos en reflejarlo; si hay más páginas, la petición guarda el cursor y puedes repetirla para recorrerlas. Si no aparece y ya se recorrieron todas las páginas, reinicia el listado poniendo `documentos_siguiente` en blanco y vuelve a probar tras esperar unos segundos.
5. **Solicitar enlace:** el backend valida la identidad, el tenant y el cliente; devuelve un enlace temporal de 60 segundos.
6. **Descargar:** ejecútalo dentro de esos 60 segundos. Comprueba que el contenido sea `Prueba de documento CRM SaaS.`. Si caducó, repite los pasos 5 y 6. El enlace es temporal y permite descargar el archivo a quien lo posea durante su vigencia.
7. **Sin token:** se espera rechazo 401. Si API Gateway devuelve otro código de rechazo, revisar su configuración y documentarlo.
8. **Login B:** verifica que el tenant sea distinto del tenant A.
9. **Listar como B:** con el ID de cliente A, debe responder 404.
10. **Descargar como B:** con el cliente y documento de A, debe responder 404, sin entregar una URL.

Si falla la subida, revisa los logs de `crm-clientes-dev-subirDocumento` y los permisos S3 y DynamoDB de `LabRole`. Si falla el login o la consulta protegida, revisa los logs de `crm-usuarios-dev-loginUsuario` y `crm-compartido-dev-authorizer`, así como el acceso a Parameter Store/KMS. No publiques los valores de parámetros, tokens, contraseñas ni URLs firmadas. Los mensajes de error de las Lambdas son deliberadamente genéricos.

El login y el acceso protegido comprueban el flujo funcional con Parameter Store después de desplegar el código nuevo; además se puede verificar en la configuración de ambas Lambdas que `JWT_SECRET_PARAMETER` apunte a `/crm/dev/jwt-secret`. Las pruebas en Postman no muestran el valor del parámetro ni prueban por sí solas la configuración de KMS o las políticas IAM.
