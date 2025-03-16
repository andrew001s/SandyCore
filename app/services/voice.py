from elevenlabs.client import ElevenLabs
from elevenlabs import play
from app.core.config import config
client = ElevenLabs(
    api_key=config.ELEVEN_API_KEY,
)

def play_audio(response: str):
    audio = client.text_to_speech.convert(
    text=response, voice_id='9BWtsMINqrJLrRacOk9x',model_id="eleven_multilingual_v2",
    output_format="mp3_44100_128",
    )
    play(audio)