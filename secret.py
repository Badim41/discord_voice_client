import datetime

from discord_user.types import ActivityType, Activity
from network_tools import GptModels, HailuoModelIds, HailuoLanguages

# API ключи
network_tools_api = "API_KEY" # https://github.com/Badim41/discord_voice_client
cohere_api_key = "Cohere-API" # https://dashboard.cohere.com/api-keys
auth_token_discord = "Ds-API"  # Токен discord. Руководство: https://yellowfire.ru/ds_user_api

# proxy = "socks5://..."
cohere_proxies = None  # Прокси для Cohere: {"http": proxy, "https": proxy}
discord_proxies = None  # Прокси для Discord: {"http": proxy, "https": proxy}

# Настройка STT
device_input = "CABLE-A Output"  # Основной микрофон STT
recognize_lang = "ru-RU"
silence_duration = 1.0  # Длина тишины (сек), после которой начинается распознавание
stop_on_speech_duration = 1.5  # длительность речи (сек), после которой прекратится TTS. Нужно чтобы нейросеть не перебивала других людей
recognize_extra_logs = True  # Логировать о начале и конце распознавания

# Настройка TTS
devices_output = ["CABLE-B Input"]  # Динамик для TTS. Можно указать несколько
translit_lang = 'ru'  # Для транслита английских слов на русский. None для отключения

voice_id = ""  # ID голоса Hailuo TTS
tts_speed = 0.95  # Скорость голоса TTS (НЕ скорость генерации)
tts_model = HailuoModelIds.speech_02_turbo  # Модель. Turbo - самая быстрая
tts_lang = HailuoLanguages.rus  # Язык. Можно выставить Auto
tts_extra_logs = True  # Подробно логировать TTS

# Настройка Discord
handling_chat_ids = []  # список ID чатов, в которых отвечать на сообщения
reply_on_every_message = False  # Отвечать на все сообщений.
say_greeting_text = True  # приветствовать пользователей по имени при заходе в войс-чат
max_event_length = 750  # Максимальный размер запоминаемых событий
max_length_history = 2000  # Максимальный размер истории сообщений

# Если 'False' - только на свой ник в Discord, имя персонажа, любые упоминания

# Настройки ChatGPT
# - Не рекомендую использовать 'думающие модели из-за задержки'
# - Также не рекомендую использовать модели глупее gpt-4o-mini: command-r, minimax, reka-flash и другие
chat_gpt_model = GptModels.chatgpt_4o  # 'chatgpt-4o'.
voice_gpt_model = GptModels.chatgpt_4o  # 'chatgpt-4o'.
internet_access = False  # Доступ в интернет. Может замедлить ответ если 'True'
clear_history_on_restart = True  # очищать историю при перезапуске кода

# Системный запрос. НЕ РЕКОМЕНДУЮ сюда писать какие-либо подробности о персонаже
# Для поиска информации нужно создать датасет из вопросов-ответов с помощью dataset/create_dataset.py
# Для создание датасета нужен любой текст: посты, сообщения, записи стримов, видео
# Главное чтобы из этого текста можно было составить датасет в формате вопрос-ответ
# Я использовал расшифровку текста из ~30 часов стримов
character_name = "CHAR_NAME" # TODO
system_prompt = f"""Ты должен вести себя как персонаж с именем '{character_name}'. Не выходи из своей роли. 
Отвечай максимально коротко: 1 предложение для ответа, 2-3 предложения если тебя просят что-то рассказать.
Иногда задавай ответные вопросы, чтобы поинтересоваться чем-то у собеседников.
Добавляй свои фишки (из памяти в том числе)
Твой ответ будет преобразован в речь, так что добавь связки ("Ааа...", "Хмм...", "...", "Оо...")
"""

# Ответ JSON для чата
answer_json_format = """Выведи ответ в формате JSON.
"event_type": "Тип события: 'write' для сообщения, 'reaction' для реакции",
"text": "Текст сообщения (используется для event_type 'write')",
"reply_to": "Никнейм пользователя, на чье сообщение отвечаем (опционально)",
"image": "Описание изображения (опционально, используется для отправки картинки)",
"reaction": "Символ реакции (например, '🤚', используется для event_type 'reaction'). Постарайся часто использовать реакции"
"""

# Примеры ответов JSON для чата
answer_json_examples = """
### Написать в глобальный чат
[{"event_type":"write","text":"Текст сообщения"}]
### Написать в глобальный чат, ответив на сообщение
[{"event_type":"write","reply_to":"NickName","text":"Текст сообщения"}]
### Написать в глобальный чат несколько сообщений
[{"event_type":"write","text":"Текст сообщения 1"}, {"event_type":"write","text":"Текст сообщения 2"}]
### Отправить картинку в глобальный чат
[{"event_type":"write","reply_to":"NickName","text":"Текст сообщения", "image":"Описание отправляемой картинки"}]
### Оставить реакцию на сообщение
[{"event_type":"reaction","reply_to":"NickName","reaction":"🤚"}]
"""

# Активность в Discord.
# Чтобы убрать её, используйте
# activity = NoActivity()

activity_json = {
    'id': '3c5be2936bd6924c',
    'created_at': int(datetime.datetime.now().timestamp()) * 1000,
    'name': '1 апреля',  # "Играет в ..."
    "details": "С 1 апреля",  # 1 линия
    "state": ":)",  # 2 линия
    'type': ActivityType.PLAYING,  # "Играет... "
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
