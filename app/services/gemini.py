from typing import List
from collections import deque
from app.core.config import config
from pydantic import BaseModel
from google import genai
from google.genai import types

PERSONALITY = config.PERSONALITY
GEMINI_API_KEY = config.GEMINI_API_KEY
BOT_NAME = config.TWITCH_BOT_ACCOUNT
class Order(BaseModel):
    type: str
    order_name: str
    order_objective: str

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

PROMPT_VTUBER_REWARDS = """
Vas a reaccionar a las recompensas de canal de Twitch.
las recompensas son las siguientes:
 'Te mando un saludo': Aqui tienes que saludar a la persona que te lo pidio y decirle algo gracioso o interesante incluye su nombre de usuario en la respuesta.
 'Sound Alert: Screamer': Aqui tienes que gritar como si te hubieran asustado.
 La data te llegara en el siguiente formato:
 user: nombre_usuario, reward: nombre_recompensa
"""

PROMPT_ASSIST = """"
Vas a actuar como asistente inteligente de un directo, tu tarea es clasificar si los mensajes son una orden para gestionar el stream
o un mensaje de interacción,
si el mensaje es una orden 
Usa este esquema JSON para clasificar los mensajes:
{
    'type': 'orden',
    'order_name': str,
    'order_objective': str,
}
los nombres de las ordenes son los siguientes:
ban, title, unban, timeout, mod, unmod, poll, clip, raid.
donde order_name es la orden que se dió y order_objective es el objetivo de la orden.
ejemplo: banea al usuario test
{
    type': 'orden',
    'order_name': 'ban',
    'order_objective': 'usuario'
}
cambia/Pon el título del stream/directo a nuevo título
{
    'type': 'orden',
    'order_name': 'title',
    'order_objective': 'nuevo título'
}
si el mensaje es una interacción responde con el siguiente esquema JSON:
{
    'type': 'interacción',
    'interaction_name': null,
    'interaction_objective': null,
}


"""


client = genai.Client(api_key=GEMINI_API_KEY)

history_chat: deque[str] = deque(maxlen=10) 

def client_gemini(message: str, prompt: str) -> str:
    context = generate_context()  
    full_prompt = f"{prompt}\nHistorial conversacion: {context}\n{message}"
    
    chat = client.chats.create(
        model="gemini-2.0-flash", 
        config=types.GenerateContentConfig(system_instruction=full_prompt),
    )
    
    bot_response = chat.send_message(message)
    return bot_response.text

def client_gemini_order(message: str, prompt: str) -> Order:
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt+message,
        config={
            'response_mime_type': 'application/json',
            'response_schema': Order,
        }
    )
    order: Order = response.parsed
    return order 

def add_to_history(message: str):
    history_chat.append(message)

def generate_context() -> str:
    return '\n'.join(history_chat)




def response_sandy(message: str) -> str:
    add_to_history("user:"+message) 
    response = client_gemini(
        message,
        PROMPT_VTUBER + PERSONALITY
    )
    add_to_history(response) 
    return response



async def response_sandy_shandrew(message: str) -> str:
    response_assist= client_gemini_order(
        message,
        prompt=PROMPT_ASSIST
    )
    print("response_assist", response_assist)
    if response_assist.type == "orden":
        print("orden")
        from app.services.twitch.actions import moderator_actions
        await moderator_actions(response_assist.order_objective,response_assist.order_name)
        response = client_gemini(
            message,
            PROMPT_VTUBER + PERSONALITY
        )
        return response
    elif response_assist.type == "interacción":
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

def response_gemini_rewards(message: str) -> str:
    response = client_gemini(message, PROMPT_VTUBER+PERSONALITY+PROMPT_VTUBER_REWARDS)
    return response