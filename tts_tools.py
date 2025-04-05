import os
import queue
import threading
import time

try:
    import sounddevice as sd
    import soundfile as sf
    from transliterate import translit
except Exception as e:
    print(f"Cant import one of: sounddevice, soundfile, transliterate. TTS module wont work. Error: {e}")

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
                # logger.logging(f"got audio_file: {audio_file}, created at: {creation_time}")

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
        # logger.logging("got mp3_filepath", mp3_filepath)
        def play_sound_wrapped(device_index):
            nonlocal data
            time_stop_playing = float(sql_database.get('time_stop_playing', 0))
            if time_stop_playing > creation_time:
                logger.logging(">> Пропуск аудио")
                return

            stream = sd.play(data, samplerate, device=device_index)
            while sd.get_stream().active:
                time_stop_playing = float(sql_database.get('time_stop_playing', 0))
                if time_stop_playing > creation_time:
                    logger.logging(">> Остановлено аудио")
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


def tts_audio_with_play(text: str, speed, lang, voice_id, model_id, stop_event):
    logger.logging("Request to play")
    sql_database['time_stop_playing'] = time.time() - 1
    time_play_start = time.time()

    # Поправляем произношение
    text = text.lower()
    while text.count("хмм"):
        text = text.replace("хмм", "хм")

    if translit_lang:
        text = translit(text, translit_lang)

    model = "hailuo"

    for audio_file, status in network_client.tts_api(
            prompt=text.replace("хм", "hmmmm"),
            model=model,
            speed=speed,
            lang=lang,
            voice_id=voice_id,
            model_id=model_id
    ):
        if stop_event and stop_event.is_set():
            print("Thread interrupted after TTS")
            return
        time_stop_playing = float(sql_database.get('time_stop_playing', 0))
        if time_stop_playing > time_play_start:
            logger.logging("skip tts")
            continue
        logger.logging(f"Got TTS: {audio_file}, {status}")
        if status == "stream":
            TTSQueue.add_to_queue(audio_file)