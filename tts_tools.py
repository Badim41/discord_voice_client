import os
import queue
import threading
import time
import numpy as np

import sounddevice as sd
import soundfile as sf
from transliterate import translit

from base_classes import network_client, sql_database
import secret
from errors import DeviceNotFound
from base_logger import Logs

tts_extra_logs = secret.tts_extra_logs
logger = Logs(warnings=tts_extra_logs, name="tts-tools")

devices_output = secret.devices_output
translit_lang = secret.translit_lang

def get_device_index_by_name(device_name):
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device_name.lower() in device['name'].lower():
            return i
    raise DeviceNotFound(f"Нет такого устройства: {device_name}. Устройства: {devices}")


class TTSQueue:
    _queue = queue.Queue()
    _thread = None
    _running = False

    @classmethod
    def _process_queue(cls):
        while cls._running:
            try:
                audio_file, creation_time = cls._queue.get(timeout=1)
                logger.logging(f"got audio_file: {audio_file}, created at: {creation_time}")

                time_stop_playing = float(sql_database.get('time_stop_playing', 0))
                if time_stop_playing > creation_time:
                    logger.logging(f"Skipping {audio_file} due to time_stop_playing")
                    try:
                        os.remove(audio_file)
                    except:
                        pass
                    cls._queue.task_done()
                    continue

                cls.play_sound_v2(audio_file, creation_time)
                try:
                    os.remove(audio_file)
                except:
                    pass
                cls._queue.task_done()
            except queue.Empty:
                continue

    @classmethod
    def start(cls):
        if cls._thread is None or not cls._thread.is_alive():
            cls._running = True
            cls._thread = threading.Thread(target=cls._process_queue, daemon=True)
            cls._thread.start()

    @classmethod
    def stop(cls):
        cls._running = False
        if cls._thread:
            cls._thread.join()

    @classmethod
    def add_to_queue(cls, audio_file: str):
        creation_time = time.time()
        cls._queue.put((audio_file, creation_time))

    @staticmethod
    def play_sound_v2(mp3_filepath, creation_time):
        logger.logging("got mp3_filepath", mp3_filepath)

        def apply_fadeout(data, fade_samples=4410):  # 0.1 сек при 44100 Hz
            fade = np.linspace(1.0, 0.0, fade_samples)
            data[-fade_samples:] *= fade
            return data

        def play_sound_wrapped(device_index):
            nonlocal data
            time_stop_playing = float(sql_database.get('time_stop_playing', 0))
            if time_stop_playing > creation_time:
                logger.logging("Stop play 1")
                return

            stream = sd.play(data, samplerate, device=device_index)
            while sd.get_stream().active:
                time_stop_playing = float(sql_database.get('time_stop_playing', 0))
                if time_stop_playing > creation_time:
                    logger.logging("Stop play 2 with fade-out")
                    # Применяем fade-out к последним 0.1 секундам
                    current_position = sd.get_stream().time * samplerate
                    remaining_samples = len(data) - int(current_position)
                    fade_samples = min(4410, remaining_samples)  # Не более оставшихся семплов
                    if fade_samples > 0:
                        fade = np.linspace(1.0, 0.0, fade_samples)
                        data[-fade_samples:] *= fade
                    time.sleep(0.1)  # Даем время на затухание
                    sd.stop()
                    return
                time.sleep(0.1)
            sd.wait()

        data, samplerate = sf.read(mp3_filepath)
        sd.wait()

        devices_output_index = [get_device_index_by_name(device_output) for device_output in devices_output]
        threads = [threading.Thread(target=play_sound_wrapped, args=(index,)) for index in devices_output_index]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()


def tts_audio_with_play(text: str, speed, lang, voice_id, model_id):
    logger.logging("Request to play")
    time_play_start = time.time()

    if translit_lang:
        text = translit(text, translit_lang)

    model = "hailuo"
    for audio_file, status in network_client.tts_api(
            prompt=text.lower(),
            model=model,
            speed=speed,
            lang=lang,
            voice_id=voice_id,
            model_id=model_id
    ):
        time_stop_playing = float(sql_database.get('time_stop_playing', 0))
        if time_stop_playing > time_play_start:
            logger.logging("skip tts")
            continue
        logger.logging(f"Got TTS: {audio_file}, {status}")
        if status == "stream":
            TTSQueue.add_to_queue(audio_file)