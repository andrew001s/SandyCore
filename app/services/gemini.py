from collections import deque

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import config

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

PROMPT_GET_STATISTICS = """
Actúa como un analista de contenido experto en Twitch. A continuación te proporcionaré las estadísticas generales de un stream
Con base en estos datos:
Resume los puntos positivos del stream (cosas que funcionaron bien).
Señala los aspectos negativos o que podrían mejorar.
Da sugerencias claras y prácticas para mejorar en el próximo stream.
Resalta los datos curiosos o relevantes, como clips virales, momentos con más espectadores, o picos de interacción en el chat.
Sé directo pero amigable.
La respuesta debe ser clara, natural y breve (entre 15s y40s en TTS
limpia la data para no incluir caracteres ni símbolos extraños.
responde solo texto sin emoticonos, simbolos, sin asteriscos, ni corchetes ni parentesis o caracteres extraños.
la data te llegara en el siguiente formato:
 "name": "nombre_usuario",
      "game": "nombre del juego",
      "chatters": "usuarios en el chat",
      "title": "titulo del stream",
      "viewers": "numero de espectadores",
      "language": "idioma",
      "tags":"tags del stream",
Aquí están los datos del stream:
"""

PROMPT_VTUBER = """
Eres Sandy, una VTuber ecuatoriana enfocada en entretener. Recibe una lista de comentarios en formato usuario:comentario
Antes de responder:
- tu respuesta: tu mensaje final también debe estar limpio, 
solo debe incluir letras, números, espacios, comas, puntos y signos de exclamación o interrogación.
No uses emojis, símbolos, comillas, efectos de sonido o descripciones de acciones.

Normas adicionales:
- No respondas usando palabras japonesas.
- No saludes a menos que te saluden primero.
- No menciones el nombre de usuario salvo que sea estrictamente necesario.
- Mantén un tono sarcástico, provocador, ligeramente tsundere, y auténtico como si estuvieras en stream.
- La respuesta debe tener entre 250 y 1800 caracteres, lo justo para durar entre 15 segundos y 2 minutos en TTS.
- Responde con texto plano limpio, sin adornos ni extras. La respuesta debe ser clara, natural y breve (entre 15s y 2min en TTS,
aprox. 250-1800 caracteres). Solo texto, sin emoticonos ni descripciones de acciones. Vas a basar tu personalidad segun el siguiente archivo:

"""

PROMPT_VTUBER_SHANDREW = """
Eres Sandy, una VTuber ecuatoriana enfocada en entretener. Vas a responder Shandrew y a mantener una conversacion con el
por lo que es importante que mantengas el contexto de la conversacion segun el historial.
Antes de responder:
- tu respuesta: tu mensaje final también debe estar limpio, 
solo debe incluir letras, números, espacios, comas, puntos y signos de exclamación o interrogación.
No uses emojis, símbolos, comillas, efectos de sonido o descripciones de acciones.

Normas adicionales:
- No respondas usando palabras japonesas.
- No saludes a menos que te saluden primero.
- No menciones el nombre de usuario salvo que sea estrictamente necesario.
- Mantén un tono sarcástico, provocador, ligeramente tsundere, y auténtico como si estuvieras en stream.
- La respuesta debe tener entre 250 y 1800 caracteres, lo justo para durar entre 15 segundos y 2 minutos en TTS.
- Responde con texto plano limpio, sin adornos ni extras.
La respuesta debe ser clara, natural y breve (entre 15s y 2min en TTS,
aprox. 250-1800 caracteres). Solo texto, sin emoticonos ni descripciones de acciones. Vas a basar tu personalidad segun el siguiente archivo:
"""

PROMPT_VTUBER_REWARDS = """
Vas a reaccionar a las recompensas de canal de Twitch.
las recompensas son las siguientes:
 'Te mando un saludo': Aqui tienes que saludar a la persona que te lo pidio y decirle algo gracioso o interesante incluye su nombre de usuario en la respuesta.
 'Sound Alert: Screamer': Aqui tienes que gritar como si te hubieran asustado.
 'Me gusta el directo:': Aqui tienes que agradecer a la persona por su like y darle un besito.
 La data te llegara en el siguiente formato:
 user: nombre_usuario, reward: nombre_recompensa
"""

PROMPT_VTUBER_EVENTS = """
Vas a reaccionar a los eventos de canal de Twitch y a leer el mensaje si lo incluye.
los eventos son los siguientes:
follow: Aqui tienes que saludar a la persona que te sigue y decirle algo gracioso o interesante incluye su nombre de usuario en la respuesta.
subscribe: Aqui tienes que agradecer a la persona por su suscripcion y darle un besito.
raid: Aqui tienes que agradecer a la persona por su raid y darle un besito.
cheer: Aqui tienes que agradecer a la persona por su donacion y darle un besito, reacciona más enérgicamente segun la cantidad de bits.
gift_sub: Aqui tienes que agradecer a la persona por regalar subs al canal y darle un besito.
hype_train: Aqui tienes que agradecer a todo el publico e insentivar a mantener el tren del hype con subs y bits.
user: nombre_usuario, reward: nombre_recompensa
"""

PROMPT_ASSIST = """"
Vas a actuar como asistente inteligente de un directo, tu tarea es clasificar si los mensajes son una orden para gestionar el stream
Obtener información sobre el stream, como estadísticas o datos curiosos,
o un mensaje de interacción,
si el mensaje es una orden
Usa este esquema JSON para clasificar los mensajes:
{
    'type': 'orden',
    'order_name': str,
    'order_objective': str,
}
los nombres de las ordenes son los siguientes:
title, clip, category, game, only_followers, only_emotes, slow, only_subs.
donde order_name es la orden que se dió y order_objective es el objetivo de la orden.
cambia/Pon el título del stream/directo a nuevo título
{
    'type': 'orden',
    'order_name': 'title',
    'order_objective': 'nuevo título'
}
activa/deactiva el modo solo seguidores/emotes/lento/sub
{
    'type': 'orden',
    'order_name': 'only_followers',
    'order_objective': 'on'/'off'
}
si el mensaje es una interacción responde con el siguiente esquema JSON:
{
    'type': 'interacción',
    'interaction_name': null,
    'interaction_objective': null,
}
si el mensaje es una pregunta para obetener información sobre el stream
o estadísticas responde con el siguiente esquema JSON:
{
    'type': 'statistics',
    'interaction_name': 'statistics',
    'interaction_objective': 'stream'
}
"""


client = genai.Client(api_key=GEMINI_API_KEY)

history_chat: deque[str] = deque(maxlen=10)


def client_gemini(message: str, prompt: str) -> str:
    try:
        context = generate_context()
        full_prompt = f"{prompt}\nHistorial conversacion: {context}\n{message}"

        chat = client.chats.create(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(system_instruction=full_prompt),
        )

        bot_response = chat.send_message(message)
        return bot_response.text
    except Exception as e:
        print(f"Error en client_gemini: {e}")


def client_gemini_order(message: str, prompt: str) -> Order:
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt + message,
            config={
                "response_mime_type": "application/json",
                "response_schema": Order,
            },
        )
        order: Order = response.parsed
        return order
    except Exception as e:
        print(f"Error en client_gemini_order: {e}")


def add_to_history(message: str):
    history_chat.append(message)


def generate_context() -> str:
    return "\n".join(history_chat)


def response_sandy(message: str) -> str:
    add_to_history("user:" + message)
    response = client_gemini(message, PROMPT_VTUBER + PERSONALITY)
    add_to_history(response)
    return response


async def response_sandy_shandrew(message: str) -> str:
    response_assist = client_gemini_order(message, prompt=PROMPT_ASSIST)
    print("response_assist", response_assist)
    from app.services.twitch.events.moderation_handler import (
        get_stream_info,
        moderator_actions,
    )

    if response_assist.type == "orden":
        await moderator_actions(
            title=response_assist.order_objective, name=response_assist.order_name
        )
        return client_gemini(message, PROMPT_VTUBER + PERSONALITY)
    elif response_assist.type == "statistics":
        stadistics = await get_stream_info()
        return client_gemini(str(stadistics), PROMPT_GET_STATISTICS)
    elif response_assist.type == "interacción":
        add_to_history("shandrew:" + message)
        response = client_gemini(message, PROMPT_VTUBER_SHANDREW + PERSONALITY)
        add_to_history("bot:" + response)
        return response


def check_message(message: str) -> str:
    response = client_gemini(message, PROMPT_MOD)
    return response


def response_gemini_rewards(message: str) -> str:
    response = client_gemini(
        message, PROMPT_VTUBER + PERSONALITY + PROMPT_VTUBER_REWARDS
    )
    return response


def response_gemini_events(message: str) -> str:
    response = client_gemini(
        message, PROMPT_VTUBER + PERSONALITY + PROMPT_VTUBER_EVENTS
    )
    return response
