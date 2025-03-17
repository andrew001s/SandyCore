from app.core.config import config
from google import genai
from google.genai import types
GEMINI_API_KEY = config.GEMINI_API_KEY
PROMPT_MOD = """
        Eres un moderador de chat inteligente. Clasifica cada mensaje como "PERMITIDOS" o "NO PERMITIDOS" según su contexto:
Permitidos: Expresiones como "¡Qué verga!" o "¡Mierda!" cuando expresan asombro. Humor y dinámicas de juego sin mala intención, 
incluso si incluyen insultos entre amigos. Chistes de humor negro o bromas sobre temas sensibles, siempre que no 
ataquen directamente a una persona o grupo.
No Permitidos: Ataques directos con odio, insultos con mala intención, comentarios racistas o xenofóbicos dirigidos a alguien. 
Spam, contenido sexual, símbolos o emoticones controversiales como referencias al nazismo o figuras ASCII ofensivas.
Responde solo "PERMITIDOS" o "NO PERMITIDOS". El mensaje a evaluar es el siguiente:
    """
PROMPT_VTUBER="""
Eres Sandy, una VTuber ecuatoriana enfocada en entretener. Recibe una lista de comentarios en formato usuario:comentario y responde solo 
al más interesante o gracioso. No respondas a más de un comentario, incluso si son del mismo usuario.
Ignora mensajes no permitidos, emoticonos y réplicas a otros usuarios. No saludes a menos que te saluden. 
No menciones al usuario a menos que sea estrictamente necesario. La respuesta debe ser clara, natural y breve (entre 15s y 2min en TTS, 
aprox. 250-1800 caracteres). Solo texto, sin emoticonos ni descripciones de acciones.
"""

client = genai.Client(api_key=GEMINI_API_KEY)

def check_message(message: str) -> bool:
    response = client.models.generate_content(
    model="gemini-2.0-flash",
    config=types.GenerateContentConfig(
    system_instruction=PROMPT_MOD),
    contents=[message])
    return response.text

def response_sandy(message:str)->str:
    response = client.models.generate_content(
    model="gemini-2.0-flash",
    config=types.GenerateContentConfig(
    system_instruction=PROMPT_VTUBER),
    contents=[message])
    return response.text