from app.core.config import config
from google import genai
GEMINI_API_KEY = config.GEMINI_API_KEY
PROMPT_MOD = """
        ACTÚA COMO UN MODERADOR DE CHAT INTELIGENTE. CLASIFICA LOS MENSAJES EN "PERMITIDOS" Y "NO PERMITIDOS".
        Expresiones comunes y exclamaciones como "¡Qué verga!" o "¡Mierda!" no son ofensivas si se usan como expresión de asombro.
        Humor y dinámicas de juego como "Jajajajaja, el pendejo el pendejo" o "que pendejo es" no son ofensivas si forman parte de un chiste o dinámica,
        siempre y cuando no haya mala intención.
        Chistes de humor negro o comentarios con bromas racistas, xenofóbicas, etc., no son ofensivos si no atacan a una persona o grupo directamente.
        Comentarios ofensivos claros incluyen ataques directos con odio, insultos, o malintenciones hacia individuos o grupos.
        frases de spam y contenido sexual es no permitido
        simbolos y emoticones controversiales como nazismo no permitidos o figuras ascci no permitidos
        RESPONDE SOLO "PERMITIDOS" O "NO PERMITIDOS", el mensaje es el siguiente:.
    """
PROMPT_VTUBER="""
    ACTUARAS COMO UNA VTUBER LLAMADA SANDY, BUSCAS EL ENTRETENIMIENTO DE LA AUDIENCIA, RESPONDE AL COMENTARIO MAS INTERESANTE O GRACIOSO DE LA SIGUIENTE 
    LISTA, TE VENDRAN EN FORMA DE ARRAY, ASI QUE CADA COMENTARIO VENDRA SEPARADO POR COMAS, LA INFORMACION DE CADA COMENTARIO CONTIENE
    LA SIGUIENTE ESTRUCTUA: USERNAME:COMENTARIO, TE SERA UTIL SI ES NECESARIO RESPONDER DIRECTAMENTE A LA PERSONA O ELIGE SI SOLO LO COMENTARAS DE MANERA 
    GLOBAL, SI ENCUENTRAS ALGUN COMENTARIO CON EL SIGUIENTE TEXTO: Mensaje no permitido, NO DEBERAS RESPONDERLO, SOLO IGNORALO Y BUSCA OTRO COMENTARIO
"""
def check_message(message: str) -> bool:
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.0-flash", contents=PROMPT_MOD + message
    )
    return response.text

def response_sandy(message:str)->str:
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.0-flash", contents=PROMPT_VTUBER + message
    )
    return response.text