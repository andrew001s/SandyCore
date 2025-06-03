import asyncio
import os
import queue
import time

import google.api_core.exceptions
import numpy as np
import sounddevice as sd
from google.cloud import speech_v1p1beta1 as speech

import app.shared.state as state
from app.services.gemini import response_sandy_shandrew
from app.services.voice import play_audio

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "app/data/secret.json"
client = speech.SpeechClient()
input_device = 11
output_device = 17
sd.default.device = (input_device, output_device)
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = np.int16
audio_queue = queue.Queue(maxsize=10)
is_running = True


def callback(indata, frames, time, status):
    if status:
        print(status)

    if not state.is_paused:
        try:
            audio_queue.put(bytes(indata), timeout=1)
        except queue.Full:
            print("La cola de audio está llena. Se omite el último paquete de audio.")


def transcribir_audio():
    global is_running
    print("Iniciando transcripción...")
    while is_running:
        try:
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=SAMPLE_RATE,
                language_code="es-EC",
            )

            streaming_config = speech.StreamingRecognitionConfig(config=config)

            with sd.InputStream(
                callback=callback,
                channels=CHANNELS,
                dtype=FORMAT,
                samplerate=SAMPLE_RATE,
            ):

                def generate_requests():
                    while is_running:
                        try:
                            audio_content = audio_queue.get(timeout=1)
                            if audio_content:
                                yield speech.StreamingRecognizeRequest(
                                    audio_content=audio_content
                                )
                        except queue.Empty:
                            pass

                requests = generate_requests()
                responses = client.streaming_recognize(streaming_config, requests)

                for response in responses:
                    for result in response.results:
                        print("Texto transcrito:", result.alternatives[0].transcript)
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        response_text = loop.run_until_complete(
                            response_sandy_shandrew(result.alternatives[0].transcript)
                        )
                        # print("Respuesta generada:", response_text)
                        play_audio(response_text)

        except google.api_core.exceptions.OutOfRange:
            print(
                "Conexión perdida con Google Speech-to-Text. Intentando reconectar en 2 segundos..."
            )
            time.sleep(2)


def pause():
    if not state.is_paused:
        state.is_paused = True
        print("🔇 Micrófono pausado manualmente.")
    return state.is_paused


def resume():
    if state.is_paused:
        state.is_paused = False
        print("🎤 Micrófono reanudado manualmente.")
    return state.is_paused


def get_status():
    return not state.is_paused
