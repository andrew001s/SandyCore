# Sandy sin marca: compra única de US$3

Estado: integración preparada, deshabilitada por defecto. No se ha creado un producto, configurado una cuenta mercantil, aplicado la migración remota ni realizado un cobro.

## Alcance

Beneficio personal asociado al ID de cuenta Clerk: retirar el aviso de apoyo en PNG, Live2D, VRM y sus fuentes de OBS. Pago único, sin suscripción, USD, interfaz en español. La comprobación requiere internet. No cambia las otras funciones gratuitas. Una donación voluntaria no compra este beneficio.

## Activación en un entorno de prueba

1. Revisar y aplicar, en este orden, `supabase/migrations/20261106000000_support_purchases.sql` y `supabase/migrations/20261106010000_support_verified_emails.sql` con una cuenta administradora. Ejecutar `tests/sql/support_purchases.sql` únicamente después de aplicar ambas migraciones y siempre en una base desechable.
2. Crear en Ko-fi Shop un producto digital de precio fijo US$3, una unidad, sin variantes, sin descuentos ni suscripción. Explicar que el beneficio requiere iniciar la compra desde Sandy y tener verificado en Sandy el correo usado en Ko-fi.
3. Configurar en el servidor `KOFI_WATERMARK_PRODUCT_CODE` y `KOFI_VERIFICATION_TOKEN`. No introducir valores secretos en variables `NEXT_PUBLIC_*`.
4. Generar DOS claves aleatorias independientes de al menos 32 caracteres: `SUPPORT_BILLING_SECRET` y `SUPPORT_OVERLAY_SECRET`. Guardarlas junto con las credenciales actuales de Clerk y Supabase. No reutilizar claves de otros servicios.
5. Configurar la URL HTTPS pública `https://BACKEND/support/ko-fi/webhook` en Ko-fi.
6. Activar `KOFI_WATERMARK_ENABLED=true`, probar el webhook y después hacer una compra real controlada.
8. Solo después habilitar en producción. El frontend usa la URL de backend ya configurada, sin credenciales nuevas públicas. Si falta alguna clave, la compra queda no disponible.

## Asociación y recuperación

`POST /support/checkout` exige sesión Clerk y registra un intento de una hora. El cliente no elige usuario, precio, moneda ni correo. Ko-fi notifica el pago al webhook y el backend lo valida antes de conceder el beneficio.

La consulta autenticada vincula la compra cuando coincide cualquier correo verificado
actual y el pago ocurre dentro de la ventana del intento. Si el usuario pagó con otro
correo, debe añadirlo y verificarlo en su cuenta de Sandy y pulsar «Comprobar estado».
La titularidad ya vinculada permanece asociada al ID de cuenta, aunque cambie el correo.
No se debe pedir al usuario que vuelva a pagar ante una demora. Los reportes de error de
las rutas `/support/` se excluyen de Rollbar para no exportar cuerpos ni recibos.

## OBS y sincronización

El visor copia un enlace con credencial de lectura limitada en el fragmento `#support=...`, incluso antes del pago. No contiene una sesión Clerk, email, ID de cuenta ni permiso de modificación. El overlay mueve la credencial a sessionStorage y limpia el fragmento de la barra; las rutas de overlay excluyen la inicialización de analítica. La consulta pública usa POST sin cookies y devuelve únicamente `watermark_free`. Tratar el enlace como privado: compartirlo comparte el beneficio visual, aunque no da acceso a la cuenta.

La cuenta consulta pagos pendientes cada 3 s inicialmente y después cada 15 s. Los permisos activos y OBS se consultan cada 60 s y al recuperar foco o conexión. Ante error, se muestra la marca hasta verificar de nuevo. Los enlaces antiguos sin credencial requieren copiarse una vez. La rotación desde la interfaz incrementa la revisión del permiso e invalida los enlaces anteriores; copiar los nuevos después.

`SUPPORT_BILLING_SECRET` debe ser estable y respaldarse. Se puede rotar `SUPPORT_OVERLAY_SECRET` de forma independiente; invalida globalmente enlaces OBS y exige copiarlos de nuevo. Preferir la rotación por cuenta desde la interfaz.

## Devoluciones, disputas y reconciliación

Ko-fi ofrece notificaciones de pagos, pero no se presupone un evento automático de devolución. Revisar las devoluciones y disputas reales en el proveedor y registrar cada una.

Desde el backend con sus credenciales de servidor, tras verificar la transacción en el proveedor:

```powershell
python -m scripts.reconcile_support_payment --transaction-id ID_DEL_RECIBO --state refunded --actor operador --reason "Devolución confirmada en el proveedor"
# Para una disputa confirmada: --state disputed
```

Consultar `python -m scripts.reconcile_support_payment --help` para la sintaxis exacta. El comando solo revoca, no concede beneficios; registra actor, motivo y estado anterior. Un webhook repetido no reactiva una devolución. La revocación llega a sesiones abiertas en la siguiente consulta (normalmente hasta 60 s si hay conexión). No exponer la clave service-role ni esta operación como endpoint público. El proceso de devolución comercial sigue realizándose en el proveedor; este comando no devuelve dinero.

## Validación local

`python -m unittest discover -s tests -p test_support_billing.py` cubre autenticación, validación de notificaciones, minimización de datos, límites y permisos OBS. `tests/sql/support_purchases.sql` comprueba asociación, recuperación, no reasignación, doble aviso, revocación, auditoría y restricciones de roles sobre PostgreSQL real o compatible. Las pruebas no realizan cobros ni acceden al proveedor.

La protección evita concesiones desde el cliente y limita el acceso a los registros. Un usuario que modifica su propio navegador todavía puede alterar su representación local; no se promete protección contra manipulación del cliente. Los límites en memoria del proceso no sustituyen los límites y alertas del proxy en despliegues con múltiples réplicas.

Referencias: [API/webhooks de Ko-fi](https://help.ko-fi.com/hc/en-us/articles/360004162298-Does-ko-fi-have-an-API-or-webhook), [Ko-fi Shop](https://help.ko-fi.com/hc/en-us/articles/360009712917-Ko-fi-Shop-Sell-digital-physical-products).na autenticada de webhooks antes de activar.
