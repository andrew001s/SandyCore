from fish_audio_sdk import WebSocketSession, TTSRequest
from app.core.config import config
from pydub import AudioSegment
import io
import simpleaudio as sa

ws_session = WebSocketSession(config.FISH_API_KEY)

def stream(text):
    for line in text.split():
        yield line + " "

def play_audio(response: str):
    tts_request = TTSRequest(
        text="",
        reference_id=config.ID_VOICE,
    )

    try:
        audio_buffer = io.BytesIO()

        for chunk in ws_session.tts(tts_request, stream(response), backend="speech-1.5"):
            audio_buffer.write(chunk)

        audio_buffer.seek(0)
        audio = AudioSegment.from_mp3(audio_buffer)

        play_obj = sa.play_buffer(audio.raw_data, num_channels=audio.channels,
                                  bytes_per_sample=audio.sample_width, sample_rate=audio.frame_rate)
        play_obj.wait_done()

    except Exception as e:
        print("Error:", e)
