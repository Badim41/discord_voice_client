class TtsErrors(Exception):
    """Базовая ошибка TTS"""


class DeviceNotFound(TtsErrors):
    """Не найдено устройство для вывода аудио"""
