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

### Arquitectura

El proyecto sigue los principios de **Arquitectura Limpia (Clean Architecture)**, que permite una separación clara de responsabilidades y facilita la mantenibilidad y escalabilidad:

- **Capa de Dominio**: Contiene la lógica de negocio central, entidades y reglas de negocio independientes de cualquier framework o tecnología.
  - `app/domain/`: Definiciones de excepciones y mensajes del sistema.
  - `app/models/`: Modelos de datos y entidades del dominio.

- **Capa de Aplicación (Casos de Uso)**: Implementa la lógica de aplicación y coordina el flujo de datos entre las capas.
  - `app/core/use_cases/`: Casos de uso específicos (autenticación, perfil, tokens, etc.).
  - `app/core/ports/`: Interfaces para adaptadores externos.

- **Capa de Adaptadores**: Puentes entre la aplicación y servicios o frameworks externos.
  - `app/adapters/`: Adaptadores para servicios externos (Twitch, Gemini).
  - `app/services/`: Implementación de servicios externos.

- **Capa de Infraestructura**: Frameworks, herramientas y componentes de entrega.
  - `app/controllers/`: Controladores HTTP y WebSocket para la API.
  - `app/config/`: Configuración de la aplicación.

Esta arquitectura permite:
- **Testeabilidad**: Componentes aislados y fáciles de probar.
- **Escalabilidad**: Facilidad para añadir nuevas funcionalidades sin afectar el código existente.
- **Mantenibilidad**: Cambios en frameworks o herramientas externas no afectan a la lógica de negocio.

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
     GEMINI_API_KEY=your_gemini_api_key_here
   ```

   Estas variables son necesarias para la autenticación con Twitch y servicios de IA. Asegúrate de tener las credenciales correctas y los permisos necesarios antes de ejecutar el proyecto.

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
    "message": "Sandy IA corriendo🚀"
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

### **`POST /auth`**
- **Descripción**: Autentica el usuario con Twitch utilizando tokens OAuth.
- **Parámetros**:
  - `token`: Token de acceso de Twitch
  - `refresh_token`: Token de actualización
  - `bot`: (Booleano) Indica si la autenticación es para el bot

- **Respuesta**:
```json
{
  "message": "Autenticación exitosa"
}
```

### **`GET /profile`**
- **Descripción**: Obtiene el perfil del usuario autenticado en Twitch.
- **Parámetros Query**:
  - `bot`: (Booleano, opcional) Para obtener el perfil del bot

- **Respuesta**:
```json
{
  "profile": {
    "id": 123456789,
    "username": "nombre_usuario",
    "email": "correo@ejemplo.com",
    "picProfile": "https://url-de-imagen.com/avatar.jpg"
  }
}
```

### **`GET /stop`**
- **Descripción**: Detiene los servicios en ejecución.
- **Parámetros Query**:
  - `bot`: (Booleano, opcional) Para detener servicios del bot

- **Respuesta**:
```json
{
  "message": "Servicios detenidos"
}
```

---

## Arquitectura Técnica

### Estructura de Carpetas

```
app/
├── adapters/          # Adaptadores para servicios externos
├── config/            # Configuración de la aplicación
├── controllers/       # Controladores HTTP y WebSocket
├── core/              # Casos de uso y puertos
│   ├── ports/         # Interfaces para adaptadores
│   └── use_cases/     # Implementación de casos de uso
├── data/              # Datos estáticos y configuraciones
├── domain/            # Excepciones y mensajes del dominio
├── models/            # Modelos de datos
├── services/          # Servicios externos
│   ├── application/   # Servicios de la aplicación
│   └── twitch/        # Servicios relacionados con Twitch
└── shared/            # Estado compartido y utilidades
```

### Flujo de Datos

1. Los **controladores** (`/controllers`) reciben solicitudes y las dirigen a los casos de uso apropiados.
2. Los **casos de uso** (`/core/use_cases`) implementan la lógica de negocio y coordinan entre adaptadores.
3. Los **adaptadores** (`/adapters`) conectan con servicios externos como Twitch y Gemini.
4. Los **modelos** (`/models`) definen las estructuras de datos utilizadas en toda la aplicación.

---

## Licencia

Este proyecto está bajo una **Licencia Dual**:
- **MIT License**: Permite a los usuarios hacer lo que deseen con el código, modificación y distribución, siempre que se incluya la misma licencia.
- **GPL-3.0 License**: Garantiza que cualquier distribución del código (modificado o no) esté bajo los mismos términos de la GPL-3.0.

---
