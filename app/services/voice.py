from fish_audio_sdk import Session, TTSRequest
from app.core.config import config
from pydub import AudioSegment
import io
import simpleaudio as sa
from app.shared.state import audio_lock
session = Session(config.FISH_API_KEY)

def play_audio(response: str):
    response_stream = session.tts(TTSRequest(
        reference_id=config.ID_VOICE,
        text=response,
        prosody={
            "volume": 0.8,
        }
        
    ))
    try:
        with audio_lock:
            audio_data = b''.join(response_stream)
            audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
            play_obj = sa.play_buffer(audio.raw_data, num_channels=audio.channels, bytes_per_sample=audio.sample_width, sample_rate=audio.frame_rate)
            play_obj.wait_done()
    except Exception as e:
        print(e)
