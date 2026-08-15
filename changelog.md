## v2.1.0 (2026-08-15)

### Feat

- **security**: agregar cifrado de secretos y clave de encriptación en la configuración

## v2.0.1 (2026-08-08)

### Fix

- **ci**: publicar el tag de release en vez de perderlo en el runner

## v2.0.0 (2026-08-08)

### BREAKING CHANGE

- /ws ahora exige el parámetro `token` con un token de
/stream/token; sin él la conexión se cierra con el código 1008. Un cliente
conectado deja de recibir los eventos de otras cuentas. El frontend debe pedir
el token dentro de la función de reconexión, no al montar: el token dura 300s
y solo se valida al abrir la conexión, así que una conexión establecida no se
cae al expirar, pero reconectar con un token viejo falla.

### Feat

- **realtime**: particionar el bus de eventos por usuario y autenticar /ws

## v1.3.10 (2026-08-08)

## v1.3.9 (2026-08-04)

## v1.3.8 (2026-08-03)

## v1.3.7 (2026-08-02)

## v1.3.6 (2026-08-02)

## v1.3.5 (2026-08-02)

## v1.3.4 (2026-08-02)

## v1.3.3 (2026-08-02)

## v1.3.2 (2026-08-01)

## v1.3.1 (2026-08-01)

### Feat

- ✨ integrar OpenRouter como proveedor de IA intercambiable y optimizar latencia

### Fix

- evitar que la app falle al iniciar en Vercel por imports pesados
- 🐛 Corregir la extensión del archivo de personalidad de .txt a .json

### Refactor

- **docs**: 📝 Actualizar la estructura del README y eliminar el archivo de personalidad

## v1.3.0 (2025-06-22)

### Feat

- ✨ Agregar plantillas para solicitudes de mejora y pull requests
- **personality**: ✨  Actualizar la descripción de personalidad y agregar nuevas características y normas de respuesta para la VTuber Sandy
- **auth**: ✨ simplificar la asignación de usuario_bot al obtener usuarios del bot
- **eventsub**: ✨ optimizar la configuración de EventSub para evitar instancias duplicadas y mejorar la gestión de eventos
- **auth**: ✨ agregar funcionalidad para refrescar el token de acceso y manejar excepciones de autenticación feat(chat): ✨ ajustar la inicialización del chat para almacenar la instancia de Twitch feat(start_services): ✨ mejorar la configuración de EventSub para instancias de bot y usuario
- **tokens**: ✨ agregar funcionalidad para obtener y guardar tokens de autenticación de Twitch
- **profile**: ✨ agregar funcionalidad para obtener el perfil de usuario de Twitch y manejar excepciones
- **auth**: ✨ implementar autenticación de usuario de Twitch y agregar modelo de datos para la autenticación refactor(twitch_services): ♻️ actualizar la lógica de creación de instancias de Twitch para incluir tokens refactor(twitch_router): ♻️ agregar endpoint para autenticar usuarios de Twitch
- **eventsub_handler**: ✨ agregar clase EventSubUseCase para manejar eventos de Twitch y enviar respuestas a través de WebSocket
- ✨ agregar modelos de mensajes WebSocket para manejar diferentes tipos de comunicación
- ✨ implementar adaptador WebSocket y caso de uso para manejar mensajes de chat
- ✨ agregar soporte para WebSocket y manejar conexiones en el servidor
- ✨ agregar enrutador de Gemini y servicios relacionados
- ✨ eliminar función run_bot y limpiar importaciones en el módulo de Twitch
- ✨ agregar enrutador de Twitch y servicios relacionados
- ✨ configuración CORS y agregar enrutador de pruebas
- ✨ actualizar la personalidad de Sandy con nuevos rasgos y detalles
- ✨ agregar soporte para manejar el bot de Twitch en los servicios de inicio y cierre
- ✨ evitar inicio múltiple del hilo de transcripción de audio
- ✨ agregar manejo de cierre para servicios de Twitch
- ✨ agregar endpoint para obtener el perfil de usuario
- ✨  implementar manejo de estado para conexión y pausa del micrófono

### Fix

- 🗑️ Eliminar plantillas de credenciales y estado de audio no utilizado
- **chat_handler**: :bug: Modificar la función setup_chat para aceptar una instancia de bot y actualizar su uso en el caso de servicios
- :bug: Aumentar el tamaño del chunk de mensajes a 3 y limpiar el chunk después de procesar
- :bug: Corrección setup chat y setup event sub
- 🐛 corregir el cierre del chat en el caso de uso de servicios de Twitch
- 🐛 mejorar el manejo de mensajes en el chat y agregar verificación de bots

### Refactor

- **domain**: ♻️ Reorganizar estructura de archivos y actualizar rutas de archivos de palabras prohibidas y personalidad
- **websocket_server**: 💬 Agregar emoji a mensaje de conexión establecido en el servidor WebSocket
- :recycle: eliminar archivos de servicios de transcripción y reproducción de audio
- :recycle: Refactor codebase for improved readability and maintainability
- ♻️ optimizar el manejo de servicios de Twitch en el enrutador y ajustar la lógica de inicio de servicios
- ♻️ agregar funcionalidad para cerrar servicios de Twitch y manejar excepciones en el enrutador
- ♻️ eliminar importación innecesaria de la biblioteca keyboard

## v1.2.0 (2025-04-21)

### Feat

- ✨ agregar soporte para autenticación de bot y manejo de tokens en la API de Twitch

### Fix

- 🐛 reemplazar el envío de mensajes de Twitch por el método de chat en el manejador de moderación
- 🐛 corregir la declaración de variable chat en setup_chat

### Refactor

- ♻️ actualizar el mensaje de inicio en la API a "Sandy IA corriendo🚀"

## v1.1.1 (2025-04-20)

### Refactor

- ♻️ reorganizar y modularizar el manejo de autenticación y eventos de Twitch

## v1.1.0 (2025-04-20)

### Feat

- ✨ agregar manejo de tokens para autenticación de usuario en Twitch
- ✨ agregar middleware CORS para permitir solicitudes de origen cruzado
- ✨ agregar control de pausa y reanudación del micrófono mediante endpoints

### Fix

- 🐛 agregar manejo de excepciones en las funciones client_gemini y client_gemini_order
- 🐛 manejar excepciones en las acciones del moderador
- 🐛 eliminar función check_keypress y su hilo asociado

### Refactor

- ♻️ reducir tamaño de chunk para mensajes de chat a 3

## v1.0.0 (2025-04-09)

### Feat

- ✨ agregar manejo de eventos de Twitch para seguir, suscribirse,raid y regalar subs
- ✨ agregar función para obtener estadísticas del stream y permisos de moderador
- ✨ agregar nuevas acciones de moderador y permisos para mejorar la gestión del chat en Twitch
- ✨ agregar manejo de categorías y juegos en las acciones de moderador para Twitch
- ✨ agregar nuevos permisos de usuario para mejorar la gestión del chat en Twitch
- ✨ agregar acciones de moderador para cambiar el título del stream en Twitch
- ✨ agregar manejo de órdenes y clasificaciones en el asistente de Twitch
- ✨ simplificar el endpoint /start eliminando opciones de servicio
- ✨ reorganizar importaciones y agregar manejo de acciones de moderador en Twitch
- ✨ agregar manejo de recompensas de canal de Twitch
- ✨ Create README.md
- agregar licencia dual con términos para uso comercial y no comercial

### Fix

- :bug: eliminar archivo de licencia obsoleto

### Refactor

- ♻️ eliminar importación innecesaria de Optional
- ♻️  detener instancias de chat
- ♻️ eliminar líneas en blanco innecesarias en la función de acciones de moderador
- ♻️ eliminar manejo de acciones de moderador para tipos de juego y categoría en la respuesta de Sandy
- ♻️ eliminar impresión de ID de juego en la función de cambio de juego
- ♻️ eliminar acciones de moderador del archivo de gestión en Twitch
- ♻️ Cambio de nombre de message a twitch para mejor comprension de la clase

## v0.2.0-alpha (2025-04-05)

### Feat

- agregar bloqueo asíncrono para manejar la concurrencia en el procesamiento de mensajes
- agregar plantilla de credenciales para la cuenta de servicio de Google Cloud y actualizar requisitos de dependencias
- **voice**: :sparkles: establecer el volumen a 0.5
- **personality**: ajustar la personalidad de Sandy para ser menos agresiva manteniendo el sarcasmo
- **voice**: implementar streaming de audio utilizando WebSocket
- **personality**: ajustar la personalidad de Sandy a menos agresiva
- **speech2Text**: :sparkles: Rehabilitar la reproducción de audio de la respuesta del bot
- **gemini**: :sparkles: Añadir manejo de historial de mensajes y contexto
- **personality**: :sparkles: Añadir nuevo modismo "Webada" en el archivo de personalidad
- **main**: :sparkles: Añadir función para encender/apagar el speech to text
- **personality**: :sparkles: Añadir nuevas respuestas y modismos en el archivo de personalidad
- **voice**: :sparkles: Añadir configuración de prosodia para el volumen en la reproducción de audio
- **services**: :sparkles: Añadir soporte para transcripción de audio y ejecución de servicios en segundo plano
- **moderation**: :sparkles: Mejorar la clasificación de mensajes en el moderador de chat

### Fix

- :bug:  implementar bloqueo de hilo para la reproducción de audio

### Refactor

- actualizar requisitos de dependencias
- **gemini**: eliminar comentarios innecesarios en funciones del historial
- **speech2Text**: eliminar comentarios innecesarios en el archivo de configuración

## v0.1.1-alpha (2025-03-27)

### Feat

- **audio**: :sparkles: Mejorar la reproducción de audio utilizando pydub y simpleaudio
- **voice**: :sparkles: Integrar soporte para la API de Fish Audio
- **personality**: :sparkles: Añadir soporte para la personalidad de VTuber desde un archivo de configuración
- **gemini**: :sparkles: Mejorar la generación apartir de configuracion de parámetros
- **messages**: :sparkles: Actualizar la cuenta del bot de Twitch a partir de la configuración
- **voice**: :sparkles: Añadir integración con Eleven Labs para reproducir las respuestas en audio
- **gemini**: :sparkles: Añadir soporte para respuestas de VTuber con Gemini
- **bot**: :sparkles: Refactor bot structure and add banned words moderation
- **messages**: :sparkles: test

### Fix

- **personality**: :bug: Corregir formato de respuestas en el archivo de personalidad y ajustar tamaño de chunk en el servicio de mensajes
- **personality**: :bug: Corregir la descripción de la Vtuber Sandy en el archivo de personalidad
- **messages**: :bug: Activar la reproducción de audio en la función de manejo de mensajes
- **gitignore**: :bug: Fix .gitignore to ignore python venv and OS Files

### Refactor

- **gemini**: :recycle: Mejorar la lógica de moderación de mensajes y actualizar el prompt de VTuber
- **messages**: :recycle: Forzar verificación en la autenticación del usuario
- **messages**: :recycle: Separara la lógica de gemini de la de mensajes
- **moderation**: :recycle: Update banned words list and modify moderation response logic
