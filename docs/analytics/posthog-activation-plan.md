# Propuesta de instrumentación de activación y monetización

PostHog se habilitó en noviembre de 2026. No interpretar la ausencia de eventos anteriores como ausencia de uso.

## Contrato de eventos

- `ai_response_succeeded`: emitir una vez por respuesta de IA con contenido no vacío y completada sin error. Propiedades permitidas: `provider` (gemini, openrouter, local...), `mode` (text, voice). No incluir prompts, respuestas, tokens, claves ni datos sensibles.
- `vtuber_session_started`: emitir tras confirmación de arranque exitoso del servicio, no al hacer clic ni en un reintento fallido. Si el servicio ya estaba activo, no contar una sesión nueva.
- `subscription_activated`: evento reservado a suscripciones recurrentes pagadas, emitido únicamente desde el backend al confirmar el estado activo mediante webhook firmado del proveedor de cobro o reconciliación fiable. No emitir desde el botón de checkout ni desde el frontend. Propiedades sugeridas: `plan_id`, `billing_period`, `currency` y `source`. Usar un identificador de evento estable para deduplicación. Nunca enviar datos de tarjeta o información personal.

## Distinción importante

`support_checkout_started` corresponde a Sandy Plus de Ko-fi (pago único de USD 3), no a una suscripción recurrente. `support_license_redeemed` indica canje de código y no prueba por sí solo que hubo un pago nuevo. Para medir la monetización de Sandy Plus, instrumentar por separado `support_purchase_confirmed` al confirmar el pago en el backend y evitar duplicados.

## Validaciones antes de desplegar

1. Verificar que el flujo de respuesta de IA en frontend no emita éxito por un stream parcial ni por un error de TTS.
2. Revisar todos los caminos de inicio de servicio (Twitch, Kick, YouTube), incluidos arranques automáticos y desde backend.
3. Localizar el proveedor real de suscripciones recurrentes antes de añadir el evento de activación. No confundir suscripciones a canales de Twitch/Kick con suscripciones de Sandy Studio.
4. Verificar identidad de usuario en PostHog, entorno, consentimiento y filtros de cuentas internas.
5. Construir embudos por usuarios únicos y ventana temporal de conversión, no dividiendo totales de eventos.

## Estado de esta rama

Documento de propuesta: no agrega instrumentación de pago ni modifica lógica de cobro.
