import datetime

from discord_user.types import ActivityType, Activity
from network_tools import GptModels, HailuoModelIds, HailuoLanguages

# API ключи
network_tools_api = "NETWORK_API_KEY"
cohere_api_keys = ["COHERE_API"]

auth_token_discord = "ABCCCC.DEFFF..."  # Токен discord

cohere_proxies = None  # Прокси для Cohere: {"http": proxy, "https": proxy}
discord_proxies = None  # Прокси для Discord: {"http": proxy, "https": proxy}

# Настройка STT
device_input = "CABLE-A Output"  # Основной микрофон STT
recognize_lang = "ru-RU"
silence_duration = 0.7  # Длина тишины (сек), после которой начинается распознавание
stop_on_speech_duration = 3  # длительность речи (сек), после которой прекратится TTS. Нужно чтобы нейросеть не перебивала других людей
recognize_extra_logs = False  # Логировать о начале и конце распознавания
embedding_interval = 10  # как часто будет подгружаться embedding модель (для высокой скорости)

# Настройка TTS
devices_output = ["CABLE-B Input"]  # Динамик для TTS. Можно указать несколько
translit_lang = 'ru'  # Для транслита английских слов на русский. None для отключения

voice_id = ""  # ID голоса Hailuo TTS
tts_speed = 1.0  # Скорость голоса TTS (НЕ скорость генерации)
tts_model = HailuoModelIds.speech_02_turbo  # Модель. Turbo - самая быстрая
tts_lang = HailuoLanguages.rus  # Язык. Можно выставить Auto
tts_extra_logs = True  # Подробно логировать TTS

# Настройка Discord
handling_chat_ids = ["CHAT_ID"]  # список ID чатов, в которых отвечать на сообщения
handling_guild_ids = ["None", "GUILD_ID"]  # список ID гильдий. None - ЛС
# Лимит на отправку сообщений (максимум X сообщение за X секунд)
# all - общий лимит на отправку сообщений
# "ID" - лимит на отправку сообщений в канале/гильдии
# default - лимит для ID, у которых не задан конкретный лимит
# Формат: {"ключ": {"count": 1, "time": X}}
send_message_limit = {
    "all": {"count": 3, "time": 1},  # 3 сообщения за 1 секунду
    "CHAT_ID": {"count": 1, "time": 60 * 20},  # 1 сообщение за 20 минут
    "GUILD_ID": {"count": 1, "time": 60 * 20},  # 1 сообщение за 20 минут
    "default": {"count": 1, "time": 3}  # 1 сообщение за 3 секунды
}

reply_on_every_message = False  # Отвечать на все сообщения
# Если 'False' - реагирует только на свой ник в Discord, имя персонажа или упоминание (кроме @everyone и @here)
say_greeting_text = True  # приветствовать пользователей по имени при заходе в войс-чат
max_reactions = 3  # Максимальное количество реакций на 1 сообщение
message_delay = 5  # промежуток отправки сообщений, если их несколько
max_event_length = 750  # Максимальный размер запоминаемых событий
max_length_history_messages = 15  # Максимальный размер истории (количество сообщений)
max_length_history = 2000  # Максимальный размер истории (количество символов)

# Настройки ChatGPT
# - Не рекомендую использовать 'думающие модели из-за задержки'
# - Также не рекомендую использовать модели глупее gpt-4o-mini: command-r, minimax, reka-flash и другие
chat_gpt_model = GptModels.chatgpt_4o  # 'chatgpt-4o'.
voice_gpt_model = GptModels.chatgpt_4o  # 'chatgpt-4o'.
search_dataset_model = GptModels.gpt_4o_mini  # "gpt-4o-mini". Более быстрая модель
internet_access = False  # Доступ в интернет. Может замедлить ответ если 'True'
clear_history_on_restart = False  # очищать историю сообщений (в войс-чате) при перезапуске кода

# Системный запрос. НЕ РЕКОМЕНДУЮ сюда писать какие-либо подробности о персонаже
# Для поиска информации нужно создать датасет из вопросов-ответов с помощью dataset/create_dataset.py
# Для создание датасета нужен любой текст: посты, сообщения, записи стримов, видео
# Главное чтобы из этого текста можно было составить датасет в формате вопрос-ответ
# Я использовал расшифровку текста из ~30 часов стримов, сообщения в дискорде, видео
# не заменяйте NUM_SENTENCES для автоматической регуляции
character_name = "CHAT_NAME"
system_prompt = f"""Ты должен вести себя как персонаж с именем '{character_name}'. Не выходи из своей роли. 
Отвечай максимально коротко: NUM_SENTENCES для ответа
Иногда задавай ответные вопросы, чтобы поинтересоваться чем-то у собеседников.
Ты категорически против использования нецензурной лексики, даже в завуалированном виде. Если она будет замечена, ты сообщишь, что это недопустимо, и объяснишь, почему корректное общение важно. Отвечай строго и ясно, отвергая любые формы мата.
"""
# Твой ответ будет преобразован в речь, так что добавь связки ("Ааа...", "Хмм...", "...", "Оо..." и т.д.)

# Ответ JSON для чата
answer_json_format = """Выведи ответ в формате JSON.
"event_type": "Тип события: 'write' для сообщения, 'reaction' для реакции",
"text": "Текст сообщения (используется для event_type 'write')",
"reply_to": "Никнейм пользователя, на чье сообщение отвечаем (опционально)",
"image": "Описание изображения (опционально, используется для отправки картинки)",
"reaction": "Символ реакции (например, '🤚', используется для event_type 'reaction'). Постарайся часто использовать реакции, если они уместны"
"""

# Примеры ответов JSON для чата
answer_json_examples = """
### Написать в глобальный чат
[{"event_type":"write","text":"Текст сообщения"}]
### Написать в глобальный чат, ответив на сообщение
[{"event_type":"write","reply_to":"NickName","text":"Текст сообщения"}]
### Написать в глобальный чат несколько сообщений
[{"event_type":"write","text":"Текст сообщения 1"}, {"event_type":"write","text":"Текст сообщения 2"}]
### Отправить картинку в глобальный чат. Текст запроса должен быть на английском, а текст на картинке может быть на русском. К примеру, описание на английском ("Create a logo with the text"), а текст для картинки на русском ('Кот').
[{"event_type":"write","reply_to":"NickName","text":"Вот логотип с текстов 'кот'", "image":"Logo with the text 'Кот'"}]
### Оставить реакцию с сообщением
[{"event_type":"write","text":"Привет"},{"event_type":"reaction","reply_to":"NickName","reaction":"🤚"}]
"""

search_dataset_prompt = f"""# Задача
Пользователь задаёт информацию о персонаже {character_name}
Тебе нужно найти информацию в базе данных (которая состоит из эмбеддингов вопросов)
Для этого составь вопросы, которые помогу с поиском информации. Максимум 5 конкретных вопросов

# Пример
## Пример ввода
Нарисуй себя на фоне твоего города

## Пример вывода
[
"Как выглядит твой персонаж",
"Как бы ты нарисовал своего персонажа",
"В каком стиле ты рисуешь",
"В каком городе ты живёшь"
]
"""
# Активность в Discord.
# Чтобы убрать её, используйте
# activity = NoActivity()

activity_json = {
    'id': '3c5be2936bd6924c',
    'created_at': int(datetime.datetime.now().timestamp()) * 1000,
    'name': 'на мир',  # "Играет в ..."
    "details": "А... 1 апреля прошло?",  # 1 линия
    "state": "Ну, тогда напиши мне в лс)",  # 2 линия
    'type': ActivityType.WATCHING,  # "Играет... "
    'assets': {
        'large_image': 'mp:external/iF7VVSpeuG-VuBI48Fbpx4Aa7kicLLvndebLQt6BFyc/https/yellowfire.ru/uploaded_files/github_logo.gif',
        # ссылка на картинку
        'large_text': 'Просто логотип github',  # текст при наведении на картинку
    },
    "timestamps": {
        "start": int(datetime.datetime.now().timestamp()) * 1000  # таймер
    },
    "buttons": [
        "Проект GitHub",  # название 1 кнопки
        # "Кнопка 2",  # название 2 кнопки
    ],
    'application_id': '1312148819387092993',
    "metadata": {
        "button_urls": [
            "https://github.com/Badim41/discord_voice_client",  # ссылка 1 кнопки
            # "https://...",  # ссылка 2 кнопки
        ]
    }
}

activity = Activity.from_json(activity_json)
