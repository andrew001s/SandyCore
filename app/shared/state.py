import threading
audio_lock = threading.Lock()
conected=False
is_paused = False
audio_thread_started = False