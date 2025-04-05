import asyncio
import multiprocessing
import threading
import time

import secret
from base_classes import embedding_tools, network_client, discord_client, sql_database, event_manager
from event_manager import EventTypeForManager
from ds_user import activate_handlers
from functions import format_messages, save_answer_to_history, remove_emojis
from record import AudioProcessor
from tts_tools import TTSQueue, tts_audio_with_play
from base_logger import Logs

logger = Logs(warnings=True, name="main")

system_prompt = secret.system_prompt
character_name = secret.character_name

voice_gpt_model = secret.voice_gpt_model
internet_access = secret.internet_access
max_length_history = secret.max_length_history
max_event_length = secret.max_event_length

speed = secret.tts_speed
lang = secret.tts_lang
voice_id = secret.voice_id
model_id = secret.tts_model

clear_history_on_restart = secret.clear_history_on_restart

active_threads = []  # Список кортежей: (thread, stop_event, text)


def on_speak_text_thread(text: str):
    global active_threads

    combined_text = text  # Изначально используем новый текст

    # Если есть активные потоки, объединяем их текст с новым и прерываем
    if active_threads:
        # Собираем текст от всех активных потоков
        for thread, stop_event, prev_text in active_threads:
            if thread.is_alive():
                combined_text = prev_text + " " + combined_text  # Объединяем предыдущий текст с новым
                stop_event.set()  # Устанавливаем флаг прерывания
                thread.join(timeout=0.1)  # Ждём завершения с небольшим таймаутом
        active_threads.clear()  # Очищаем список после прерывания

    # Создаём новый поток с объединённым текстом и собственным stop_event
    stop_event = threading.Event()  # Уникальный stop_event для нового потока
    new_thread = threading.Thread(target=on_speak_text, args=(combined_text, stop_event))
    active_threads.append((new_thread, stop_event, combined_text))  # Добавляем кортеж (поток, stop_event, текст)
    new_thread.start()


def on_speak_text(text: str, stop_event: threading.Event):
    # sql_database['time_stop_playing'] = time.time()
    print("on_speak_text", text)

    # Проверяем флаг прерывания перед началом длительных операций
    if stop_event.is_set():
        print("Thread interrupted before processing")
        return

    # Динамическая загрузка знаний из базы данных
    memories_character = embedding_tools.get_memories(text)
    if stop_event.is_set():
        print("Thread interrupted during memory loading")
        return

    chat_history = sql_database.get('chat_history_voice', [])
    formatted_chat_history = format_messages(chat_history, max_length=max_length_history)
    if stop_event.is_set():
        print("Thread interrupted during history formatting")
        return

    contexts = [
        EventTypeForManager.current_voice_chat_members,
        EventTypeForManager.voice_chat_text_messages,
        EventTypeForManager.voice_chat_joins
    ]
    recent_events = event_manager.get_events(contexts)
    events_text = event_manager.format_events(recent_events, max_length=max_event_length)
    if stop_event.is_set():
        print("Thread interrupted during event formatting")
        return

    full_prompt = (
        f"# Задача\n"
        f"{system_prompt}\n"
        f"Твоя речь будет преобразована в голос, так что вставляй разговорные слова и связки: 'Оо..', 'Хмм..', 'Ааа..'\n\n"
        f"{events_text}\n\n"
        f"{memories_character}\n\n"
        f"# История сообщений\n"
        f"{formatted_chat_history}\n\n"
        f"# Текущий запрос\n"
        f"{text}"
    )

    # Запрос к GPT
    answer_gpt = network_client.chatgpt_api(
        prompt=full_prompt,
        model=voice_gpt_model,
        internet_access=internet_access
    )
    if stop_event.is_set():
        print("Thread interrupted during GPT response")
        return

    response_text = remove_emojis(answer_gpt.response.text)

    chat_history = save_answer_to_history(
        chat_history=chat_history,
        prompt=text,
        user_nickname="user",
        answer=response_text,
        character_nickname=character_name
    )
    sql_database['chat_history_voice'] = chat_history
    if stop_event.is_set():
        print("Thread interrupted before TTS")
        return

    # Вывести через динамики
    tts_audio_with_play(
        text=response_text,
        speed=speed,
        lang=lang,
        voice_id=voice_id,
        model_id=model_id,
        stop_event=stop_event
    )

    # Удаляем завершившийся поток из списка активных
    current_thread = threading.current_thread()
    for thread, event, _ in active_threads:
        if thread == current_thread:
            active_threads.remove((thread, event, text))
            break


if __name__ == "__main__":
    if clear_history_on_restart:
        sql_database['chat_history_voice'] = []
        sql_database['chat_history_chat'] = []

    processor = AudioProcessor(input_device_name=secret.device_input, embedding_tools=embedding_tools)
    threading.Thread(target=processor.recognize_audio, args=(on_speak_text_thread,)).start()
    threading.Thread(target=processor.record_audio).start()

    TTSQueue.start()
    activate_handlers()

    while True:
        try:
            # Асинхронная библиотека
            loop = asyncio.get_event_loop()
            loop.run_until_complete(discord_client.start_polling())
        except Exception as e:
            logger.logging(f"Critical error: {e}")

