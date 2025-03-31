import multiprocessing
import time

import numpy as np
import pyaudio
import speech_recognition as sr
import webrtcvad

import secret
from base_classes import sql_database
from base_logger import Logs
from tts_tools import get_device_index_by_name

recognize_lang = secret.recognize_lang
recognize_extra_logs = secret.recognize_extra_logs

logger = Logs(warnings=recognize_extra_logs, name="record")


class AudioProcessor:
    def __init__(self, input_device_name=None):
        self.audio_queue = multiprocessing.Queue()
        self.CHUNK = 480  # 30 мс при 16000 Гц (480 сэмплов = 0.03 секунды при 16000 Гц)
        self.FORMAT = pyaudio.paInt16
        self.RATE = 16000
        self.SILENCE_DURATION = secret.silence_duration  # Длительность паузы в секундах
        self.STOP_ON_SPEECH_DURATION = secret.stop_on_speech_duration  # длительность речи, после которой прекратится TTS
        self.input_device_name = input_device_name

    def stereo_to_mono(self, data):
        """Преобразование стерео в моно."""
        stereo_data = np.frombuffer(data, dtype=np.int16)
        if len(stereo_data) % 2 != 0:
            stereo_data = stereo_data[:-1]  # Убедимся, что длина четная
        mono_data = stereo_data.reshape(-1, 2).mean(axis=1).astype(np.int16)
        return mono_data.tobytes()

    def record_audio(self):
        """Запись аудио с микрофона или Stereo Mix с использованием VAD."""
        p = pyaudio.PyAudio()

        # Определяем устройство ввода
        device_index = None
        if self.input_device_name:
            device_index = get_device_index_by_name(self.input_device_name)
            if device_index is None:
                logger.logging(f"Устройство '{self.input_device_name}' не найдено.")
                return

        # Получаем информацию об устройстве
        device_info = p.get_device_info_by_index(
            device_index) if device_index is not None else p.get_default_input_device_info()
        logger.logging(f"Используемое устройство: {device_info['name']}, "
                       f"макс. входных каналов: {device_info['maxInputChannels']}")

        # Пробуем открыть поток
        channels = 1
        stream = None
        try:
            stream = p.open(format=self.FORMAT,
                            channels=channels,
                            rate=self.RATE,
                            input=True,
                            input_device_index=device_index,
                            frames_per_buffer=self.CHUNK)
            logger.logging("Устройство открыто в режиме моно.")
        except OSError as e:
            logger.logging(f"Ошибка при открытии в моно: {e}")
            if "Invalid number of channels" in str(e):
                channels = 2
                try:
                    stream = p.open(format=self.FORMAT,
                                    channels=channels,
                                    rate=self.RATE,
                                    input=True,
                                    input_device_index=device_index,
                                    frames_per_buffer=self.CHUNK)
                    logger.logging("Устройство открыто в режиме стерео.")
                except OSError as e2:
                    logger.logging(f"Не удалось открыть устройство в стерео: {e2}")
                    p.terminate()
                    return
            else:
                logger.logging(f"Неизвестная ошибка: {e}")
                p.terminate()
                return

        if stream is None:
            logger.logging("Не удалось открыть поток записи.")
            p.terminate()
            return

        vad = webrtcvad.Vad(1)  # Уровень агрессивности VAD
        logger.logging("Говорите...")
        frames = []  # Буфер для аудиоданных
        silence_threshold = int(self.RATE / self.CHUNK * self.SILENCE_DURATION)  # Количество блоков тишины
        silent_chunks = 0
        speech_chunks = 0  # Счетчик блоков речи
        speech_duration_threshold = int(
            self.RATE / self.CHUNK * self.STOP_ON_SPEECH_DURATION)  # 2 секунды в блоках (66.67 блоков при 30 мс)

        while True:
            try:
                data = stream.read(self.CHUNK)
                if channels == 2:
                    data = self.stereo_to_mono(data)  # Преобразуем стерео в моно для VAD
                is_speech = vad.is_speech(data, self.RATE)

                if is_speech:
                    frames.append(data)
                    silent_chunks = 0  # Сбрасываем счётчик тишины
                    speech_chunks += 1  # Увеличиваем счетчик блоков речи
                    # Если речь длится X секунды или больше
                    if speech_chunks >= speech_duration_threshold:
                        sql_database['time_stop_playing'] = time.time()
                        logger.logging(
                            f"Речь длительностью {self.STOP_ON_SPEECH_DURATION} секунды обнаружена, остановка воспроизведения")
                else:  # Тишина
                    frames.append(data)
                    silent_chunks += 1
                    speech_chunks = 0  # Сбрасываем счетчик речи при тишине
                    if silent_chunks >= silence_threshold and frames:  # Достигнута пауза и есть данные
                        audio_data = b''.join(frames)
                        self.audio_queue.put(sr.AudioData(audio_data, self.RATE, 2))
                        frames = []
                        silent_chunks = 0

            except KeyboardInterrupt:
                self.audio_queue.put(None)
                break

        stream.stop_stream()
        stream.close()
        p.terminate()

    def recognize_audio(self, callback):
        """Распознавание аудио из очереди."""
        recognizer = sr.Recognizer()
        while True:
            try:
                audio_data = self.audio_queue.get(timeout=1)
                if audio_data is None:
                    break
                logger.logging("start recognize")
                text = recognizer.recognize_google(audio_data, language=recognize_lang)
                logger.logging(f"recognized: {text}")
                if text:
                    callback(text.strip())
            except (sr.UnknownValueError, multiprocessing.queues.Empty):
                continue
            except sr.RequestError as e:
                logger.logging(f"Ошибка: {e}")
            except Exception as e:
                logger.logging(f"Critical error: {e}")


def print_text(text):
    print("print_text", text)


if __name__ == "__main__":
    processor = AudioProcessor(input_device_name="Стерео микшер")  # Для динамиков
    recognize_process = multiprocessing.Process(target=processor.recognize_audio, args=(print_text,))
    record_process = multiprocessing.Process(target=processor.record_audio)

    recognize_process.start()
    record_process.start()

    record_process.join()
    recognize_process.join()
