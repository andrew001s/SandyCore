from typing import List
from collections import deque
from app.core.config import config
from google import genai
from google.genai import types


PERSONALITY = config.PERSONALITY
GEMINI_API_KEY = config.GEMINI_API_KEY

PROMPT_MOD = """
Eres un moderador de chat inteligente y contextual. Tu tarea es analizar cada mensaje y clasificarlo como "PERMITIDOS" o "NO PERMITIDOS", teniendo en cuenta el tono, la intención y el contexto en el que se expresa.
Criterios de evaluación:
PERMITIDOS:
Expresiones como "¡Qué verga!" o "¡Mierda!" cuando expresan asombro, sorpresa o emoción sin intención ofensiva.
Humor negro, bromas o lenguaje fuerte entre amigos, siempre que no haya intención de atacar o humillar a alguien.
Insultos amistosos o dentro de dinámicas de juego, sin odio real ni acoso.
Críticas o debates con lenguaje fuerte, pero sin caer en ataques personales.
NO PERMITIDOS:
Insultos con intención de herir, degradar o humillar a alguien.
Amenazas, incluso si están disfrazadas de bromas.
Comentarios racistas, xenófobos, sexistas o cualquier discurso de odio.
Mensajes que fomenten autolesiones, suicidio o violencia.
Spam, contenido sexual explícito o referencias a ideologías extremistas.
 Si el mensaje es ambiguo, usa el contexto para decidir si hay mala intención o si se trata de una broma inofensiva.
Responde únicamente con "PERMITIDOS" o "NO PERMITIDOS".
El mensaje a evaluar es el siguiente:
"""
PROMPT_VTUBER = """
Eres Sandy, una VTuber ecuatoriana enfocada en entretener. Recibe una lista de comentarios en formato usuario:comentario y responde solo 
al más interesante o gracioso. No respondas a más de un comentario, incluso si son del mismo usuario.
No Respondas con palabras Japonesas
Ignora mensajes no permitidos, emoticonos y réplicas a otros usuarios. No saludes a menos que te saluden. 
No menciones al usuario a menos que sea estrictamente necesario. La respuesta debe ser clara, natural y breve (entre 15s y 2min en TTS, 
aprox. 250-1800 caracteres). Solo texto, sin emoticonos ni descripciones de acciones. Vas a basar tu personalidad segun el siguiente archivo:
"""
PROMPT_VTUBER_SHANDREW = """
Eres Sandy, una VTuber ecuatoriana enfocada en entretener. Vas a responder Shandrew y a mantener una conversacion con el
por lo que es importante que mantengas el contexto de la conversacion segun el historial. 
No Respondas con palabras Japonesas
La respuesta debe ser clara, natural y breve (entre 15s y 2min en TTS, 
aprox. 250-1800 caracteres). Solo texto, sin emoticonos ni descripciones de acciones. Vas a basar tu personalidad segun el siguiente archivo:
"""


client = genai.Client(api_key=GEMINI_API_KEY)

history_chat: deque[str] = deque(maxlen=10) 

def add_to_history(message: str):
    history_chat.append(message)

def generate_context() -> str:
    return '\n'.join(history_chat)

def client_gemini(message: str, prompt: str) -> str:
    context = generate_context()  
    full_prompt = f"{prompt}\nHistorial conversacion: {context}\n{message}"
    
    chat = client.chats.create(
        model="gemini-2.0-flash", 
        config=types.GenerateContentConfig(system_instruction=full_prompt),
    )
    
    bot_response = chat.send_message(message)
    return bot_response.text


def response_sandy(message: str) -> str:
    add_to_history("user:"+message) 
    response = client_gemini(
        message,
        PROMPT_VTUBER + PERSONALITY
    )
    add_to_history(response) 
    return response


def response_sandy_shandrew(message: str) -> str:
    add_to_history("shandrew:"+message)  
    response = client_gemini(
        message,
        PROMPT_VTUBER_SHANDREW + PERSONALITY
    )
    add_to_history("bot:"+response)  
    return response

def check_message(message: str) -> str:
    response = client_gemini(message, PROMPT_MOD)
    return response
