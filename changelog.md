

## v1.1.0 (2025-04-20)

## v1.1.0 (2025-04-20)

### Feat

- ✨ agregar manejo de tokens para autenticación de usuario en Twitch
- ✨ agregar middleware CORS para permitir solicitudes de origen cruzado
- ✨ agregar control de pausa y reanudación del micrófono mediante endpoints

### Fix

- 🐛 corregir el comando de push en el flujo de trabajo de changelog para usar el token de acceso correcto
- 🐛 corregir comando de push en el flujo de trabajo de changelog para usar el token de acceso
- 🐛 actualizar configuración de git para usar secretos en lugar de valores fijos
- 🐛 agregar configuración de git antes de realizar el commit del changelog
- 🐛 corregir salida del comando git changelog para generar el archivo changelog.md
- 🐛 corregir configuración del flujo de trabajo de changelog para usar Node.js en lugar de Python
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
