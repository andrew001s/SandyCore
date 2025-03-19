from fish_audio_sdk import Session, TTSRequest
import io
import pygame
from app.core.config import config

session = Session(config.FISH_API_KEY)

def play_audio(response: str):
    response_stream = session.tts(TTSRequest(
        reference_id=config.ID_VOICE, 
        text=response
    ))

    pygame.mixer.init()

    audio_data = io.BytesIO()

    for chunk in response_stream:
        audio_data.write(chunk)

    audio_data.seek(0)

    pygame.mixer.music.load(audio_data)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)
