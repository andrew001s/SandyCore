# Proyecto: **Sandy Core IA**

![MIT License](https://img.shields.io/badge/License-MIT-green) 
![GPL-3.0 License](https://img.shields.io/badge/License-GPL_3.0-blue)  
![Google Gemini](https://img.shields.io/badge/Google_Cloud-4285F4?style=flat&logo=google-cloud&logoColor=white)
[![Python](https://img.shields.io/badge/Python-14354C?style=flat&logo=python&logoColor=white)](https://www.python.org/) 
[![Twitter](https://img.shields.io/badge/Twitch-9146FF?style=flat&logo=twitch&logoColor=white)](https://www.twitch.tv/elshandrew)  [![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=flat&logo=youtube&logoColor=white)](https://www.youtube.com/@shandrew)  [![TikTok](https://img.shields.io/badge/TikTok-000000?style=flat&logo=tiktok&logoColor=white)](https://www.tiktok.com/@elshandrew)

Este proyecto integra el modelo para una **Vtuber IA** utilizando **FastAPI** y **hilos en Python**. Puedes iniciar los servicios de forma independiente o todos a la vez mediante una API REST.

## Descripción
Proyecto que desarrolla una VTuber 2D interactiva impulsada por inteligencia artificial, capaz de responder en tiempo real a los espectadores, hablar con una voz clonada, animarse con Live2D y automatizar tareas de moderación durante transmisiones en vivo. Su objetivo es mejorar la experiencia de creadores de contenido y su audiencia mediante una interacción más natural, divertida y segura.
Este proyecto permite a los usuarios iniciar servicios de para el funcionamiento del motor de una Vtuber con IA usando **FastAPI** y **hilos de Python**. Todo el proceso es manejado por un servidor ligero y escalable que puedes controlar de forma remota a través de una API REST. Este sistema se puede utilizar para crear un bot que interactúe con el público en tiempo real.

---

## Estructura del Proyecto

```
├── app
│   ├── core
│   │   ├── bannedWords.py         # Archivo para manejar palabras prohibidas.
│   │   ├── config.py              # Archivo de configuración con ajustes globales.
│   │   └── personality.py         # Configuración de la personalidad del bot.
│   ├── data
│   │   ├── banned_words.json      # Archivo JSON con palabras prohibidas.
│   │   ├── personality.txt        # Archivo de texto con detalles sobre la personalidad.
│   │   └── secret.json            # Archivo JSON de credenciales de Google Cloud
│   ├── main.py                    # Archivo principal que ejecuta la API FastAPI.
│   ├── services
│   │   ├── gemini.py              # Servicio para interactuar con el motor de IA.
│   │   ├── messages.py            # Lógica para manejar los mensajes de twitch.
│   │   ├── moderator.py           # Lógica para moderación del chat de Twitch.
│   │   ├── speech2Text.py         # Funciones para convertir audio en texto.
│   │   └── voice.py               # Manejo de la voz del bot.
│   └── shared
│       └── state.py               # Estado compartido y manejo de hilos.
└── requirements.txt               # Lista de dependencias del proyecto.
```

---

## Instalación

### Requisitos previos

Asegúrate de tener **Python 3.8 o superior** y **pip** instalados en tu sistema.

### Pasos de Instalación

1. **Clonar el repositorio**:

   ```bash
   git clone https://github.com/andrew001s/SandyCore.git
   cd SandyCore
   ```

2. **Instalar las dependencias**:

   Puedes instalar las dependencias con el siguiente comando:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar las variables de entorno**:

   Crea un archivo `.env` en la raíz del proyecto con las siguientes variables (asegúrate de añadir tus propias claves y configuraciones):

   ```ini
     TWITCH_SECRET=your_secret_here
     TWITCH_CLIENT_ID=your_client_id_here
     TWITCH_CHANNEL=your_channel_here
     REDIRECT_URI=http://localhost:17563
     GEMINI_API_KEY=your_gemini_api_key_here
     TWITCH_BOT_ACCOUNT=your_bot_account_here
     FISH_API_KEY=your_fish_api_key_here
     ID_VOICE=your_id_voice_here
   ```

   Estas variables son necesarias para la autenticación con Twitch, configurar la cuenta del bot y otros servicios. Asegúrate de tener las credenciales correctas y los permisos necesarios antes de ejecutar el proyecto.

4. **Ejecutar el servidor**:

   Una vez que todo esté instalado y configurado, puedes ejecutar el servidor FastAPI con el siguiente comando:

   ```bash
   uvicorn app.main:app --reload
   ```

   Esto iniciará el servidor en `http://127.0.0.1:8000`.

---

---

## Endpoints Disponibles

### **`GET /`**
- **Descripción**: Endpoint raíz para verificar que el servidor está corriendo.
- **Respuesta**:
  ```json
  {
    "message": "Twitch Chat Bot corriendo con FastAPI 🚀"
  }
### **`GET /start`**

- **Descripción**: Inicia los servicios en segundo plano según el parámetro `service` proporcionado.

- **Respuesta Exitosa**: 
```json
{
  "message": "Servicios iniciados"
}
```

### **`POST /pause`**
- **Descripción**: Pausa el micrófono para detener la transcripción de audio.

- **Respuesta**:
```json
{
  "status": "Micrófono pausado",
  "paused": true
}
```
### **`POST /resume`**
- **Descripción**: Pausa el micrófono para detener la transcripción de audio.

- **Respuesta**:
```json
{
  "status": "Micrófono reanudado",
  "paused": false
}
```

### **`GET /mic-status`**
- **Descripción**: Pausa el micrófono para detener la transcripción de audio.

- **Respuesta**:
```json
{
  "status": "activo",  // o "pausado"
  "paused": false      // o true
}
```

---

## Licencia

Este proyecto está bajo una **Licencia Dual**:
- **MIT License**: Permite a los usuarios hacer lo que deseen con el código, modificación y distribución, siempre que se incluya la misma licencia.
- **GPL-3.0 License**: Garantiza que cualquier distribución del código (modificado o no) esté bajo los mismos términos de la GPL-3.0.

---
