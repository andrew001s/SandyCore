# Propuesta de instrumentación de activación y monetización

PostHog se habilitó en noviembre de 2026. No interpretar la ausencia de eventos anteriores como ausencia de uso.

## Contrato de eventos

- `ai_response_succeeded`: emitir una vez por respuesta de IA con contenido no vacío y generación completada. Propiedades permitidas: `provider`, `mode`, `interaction_type`, `llm_latency_ms`, `tts_generation_ms`, `total_latency_ms` y `tts_provider` si hubo voz. La latencia TTS es la suma de las solicitudes de síntesis; la latencia total es el tiempo transcurrido hasta completar la interacción. No incluir prompts, respuestas, tokens, claves ni datos sensibles.
- `ai_request_failed` / `ai_task_failed`: conservar errores separados por flujo; propiedades estables como `code`, `provider`, `mode` e `interaction_type` o `kind`. No enviar el texto del error ni el contenido de la interacción.
- `vtuber_session_started`: emitir tras confirmación de arranque exitoso del servicio, no al hacer clic ni en un reintento fallido. Si el servicio ya estaba activo, no contar una sesión nueva.
- `subscription_activated`: evento reservado a suscripciones recurrentes pagadas, emitido únicamente desde el backend al confirmar el estado activo mediante webhook firmado del proveedor de cobro o reconciliación fiable. No emitir desde el botón de checkout ni desde el frontend. Propiedades sugeridas: `plan_id`, `billing_period`, `currency` y `source`. Usar un identificador de evento estable para deduplicación. Nunca enviar datos de tarjeta o información personal.

## Cobertura observada en el código

- El micrófono mide respuestas de texto y voz de los proveedores configurados.
- Las respuestas de voz de Twitch, Kick y YouTube llegan al stream `speech` de SandyFront con metadata `eventsub`; el frontend puede medir una respuesta generada por mensaje de stream. El evento no diferencia todavía la plataforma de origen.
- El relay del modelo local procesa tareas de Twitch y YouTube; incluye identificador de tarea para ignorar reenvíos SSE y mide el tipo de tarea. Las tareas no identifican la plataforma de origen.
- Las respuestas de Kick en modo solo texto se envían directamente a Kick y no llegan al frontend. Requieren confirmación backend para medirlas.
- `tts_request_failed` mide fallos por proveedor TTS. No implica que haya fallado la generación LLM.
- `$ai_generation` de PostHog ya mide latencia y primer token para el proveedor local, con entrada y salida redactadas. Los campos de latencia de interacción cubren micrófono y tareas del relay local; la recepción por `speech` solo puede medir TTS porque el backend aún no transmite el tiempo de inicio de generación LLM.
- No se encontró una integración de RevenueCat ni otro proveedor de suscripciones recurrentes en SandyCore. Los eventos de ciclo de vida de suscripción quedan propuestos, no implementados.

## Embudos propuestos

Usar usuarios únicos y ventana de conversión, no comparar conteos brutos de eventos.

- **Adquisición:** `$pageview` filtrado a la landing → `sign_up_completed` → `onboarding_completed`. Verificar si el alta se registra con un evento explícito; no aparece en la instrumentación actual.
- **Activación:** `sign_up_completed` → `settings_saved` → cualquiera de `twitch_account_connected`, `kick_account_connected` o `youtube_account_connected` (paso opcional) → `vtuber_session_started` → `ai_response_succeeded`.
- **Monetización de Sandy Plus:** `pricing_viewed` → `support_checkout_started` → `support_purchase_confirmed`. Añadir `product: sandy_plus` y `purchase_type: one_time` al checkout existente. `support_purchase_confirmed` debe proceder del webhook Ko-fi ya validado, con deduplicación por transacción; no de `support_license_redeemed`.
- **Monetización recurrente (cuando exista proveedor):** `pricing_viewed` → `subscription_checkout_started` → `subscription_activated` → `subscription_renewed`; medir por separado `subscription_renewal_cancelled`, `subscription_expired` y `subscription_payment_failed`. Cancelar la renovación automática no equivale a expiración.

`pricing_viewed`, `sign_up_completed`, `support_purchase_confirmed` y los eventos recurrentes anteriores son recomendaciones, no están implementados en esta rama. No añadir eventos de cobro recurrente hasta identificar y validar el proveedor real.

## Distinción importante

`support_checkout_started` corresponde a Sandy Plus de Ko-fi (pago único de USD 3), no a una suscripción recurrente. `support_license_redeemed` indica canje de código y no prueba por sí solo que hubo un pago nuevo. Para medir la monetización de Sandy Plus, instrumentar por separado `support_purchase_confirmed` al confirmar el pago en el backend y evitar duplicados.

## Validaciones antes de desplegar

1. Verificar que el flujo de respuesta de IA en frontend no emita éxito por un stream parcial ni por un error de TTS.
2. Revisar todos los caminos de inicio de servicio (Twitch, Kick, YouTube), incluidos arranques automáticos y desde backend.
3. Localizar el proveedor real de suscripciones recurrentes antes de añadir el evento de activación. No confundir suscripciones a canales de Twitch/Kick con suscripciones de Sandy Studio.
4. Verificar identidad de usuario en PostHog, entorno, consentimiento y filtros de cuentas internas.
5. Construir embudos por usuarios únicos y ventana temporal de conversión, no dividiendo totales de eventos.

6. Validar que Clerk solo aporta el ID opaco de cuenta a PostHog; no adjuntar correo o nombre.
7. Revisar la definición de latencia: `llm_latency_ms` mide hasta el final del stream de texto; `tts_generation_ms` suma tiempos de peticiones de síntesis concurrentes y puede exceder el tiempo total.

## Estado de esta rama

Documento de propuesta: no agrega instrumentación de pago ni modifica lógica de cobro.
