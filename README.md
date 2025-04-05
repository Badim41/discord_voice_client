<p align="center">
  <img src="https://github.com/Badim41/discord_voice_client/blob/master/Logo.png?raw=true" width="300px" height="300px"/>
</p>

<h1 align="center">Discord Voice Client</h1>

<div align="center">
  <a href="https://python.org/downloads/release/python-3100/"><img src="https://img.shields.io/badge/Python-3.10-3776AB?logo=python&style=flat" alt="Python 3.10"></a>
  <a href="https://archive.org/details/vbcable-a-b-driver-pack-43"><img src="https://img.shields.io/badge/VB--Audio-Virtual%20Cable-FF5733?logo=soundcloud&style=flat" alt="VB-Audio Virtual Cable"></a>
  <a href="https://pypi.org/project/SpeechRecognition/"><img src="https://img.shields.io/badge/SpeechRecognition-4CAF50?logo=speech-recognition&style=flat" alt="SpeechRecognition"></a>
  <a href="https://github.com/wiseman/py-webrtcvad"><img src="https://img.shields.io/badge/webrtcvad-9C27B0?logo=github&style=flat" alt="webrtcvad"></a>
  <a href="https://github.com/Badim41/network_tools"><img src="https://img.shields.io/badge/NetworkToolsAPI-0f0f20?logo=github&style=flat" alt="NetworkToolsAPI"></a>
  <a href="https://github.com/Badim41/DiscordUserAPI"><img src="https://img.shields.io/badge/DiscordUserAPI-cccccc?logo=discord&style=flat" alt="DiscordUserAPI"></a>
</div>

# Описание

Этот проект представляет собой голосового и текстового ассистента. Он использует распознавание речи, обработку текста и
взаимодействие с внешними API для выполнения задач, таких как ответы на вопросы и управление Discord.

## Требования

- **Python**: 3.10
- **Установленные драйвера**:
    - Виртуальный микрофон и динамик: [VB-Audio Virtual Cable](https://archive.org/details/vbcable-a-b-driver-pack-43)
        - Рекомендуется использовать кабели A и B.
- **Устоновленный git**
- **Установленный ffmpeg**

## Стек

### Библиотеки

- **`SpeechRecognition`**  
  Используется для распознавания речи через Google Speech Recognition.  
  _Примечание_: Whisper рассматривался как альтернатива, но был отклонён из-за высоких требований к ресурсам, низкой
  скорости и недостаточного качества распознавания (модели `tiny`, `small`, `medium`). Также Whisper плохо справляется с
  русской речью. Вы можете экспериментировать с ним самостоятельно.

- **`webrtcvad`**  
  Используется для подавления шума и определения активной речи (Voice Activity Detection).

- **`sounddevice`**  
  Воспроизведение звука через виртуальный динамик.

- **`soundfile`**  
  Работа с аудиофайлами (запись и чтение).

- **`transliterate`**  
  Транслитерация английского текста в кириллицу и обратно.

### Собственные инструменты

- **`NetworkToolsAPI`**  
  API для взаимодействия с ChatGPT и Text-to-Speech (TTS).  
  Репозиторий: [NetworkToolsAPI](https://github.com/Badim41/network_tools).  
  _Рекомендуемые модели_:
    - ChatGPT: `chatgpt-4o`
    - TTS: `hailuo TTS (turbo)`

- **`DiscordUserAPI`**  
  Управление Discord через Python.  
  Репозиторий: [DiscordUserAPI](https://github.com/Badim41/DiscordUserAPI).  
  Инструкция по установке: [тут](https://yellowfire.ru/ds_user_api) (следуйте всем пунктам, кроме 4.1 и 5).


## Установка

1. Установите Python 3.10.
2. Установите виртуальные аудиокабели ([VB-Audio Virtual Cable](https://archive.org/details/vbcable-a-b-driver-pack-43)).
3. Склонируйте репозиторий:
   ```bash
   git clone https://github.com/Badim41/discord_voice_client.git
   cd discord_voice_client
   ```
4. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   pip install python-magic-bin # для windows
   ```
5. Настройте виртуальный микрофон и динамик в системе (рекомендуются кабели A и B).
6. Настройте API-ключи в secret.py
   для [NetworkTools](https://github.com/Badim41/network_tools), [Cohere](https://docs.cohere.com/cohere-documentation)
   и других сервисов (см. документацию `NetworkToolsAPI`, Cohere).
7. При необходимости замените другие настройки в secret.py

## Создание датасета

Рекомендуемый пункт. Бот будет искать ответы на вопросы в заготовленном файле с помощью эмбеддингов вопросов, тем, ответов.
### Как это работает:
Есть 2 режима. Первый быстрый, для войс-чата:
- Находится эмбеддинг вопроса и ищутся схожие вопросы в файле. Результат поиска получает GPT.
- Поиск обычно занимает ~0.5 секунд, значительно повышая качество ответа

Второй вариант занимает чуть больше времени, но намного качественнее:
- ChatGPT даётся вопрос, картинка и история сообщений, он составляет до 5 поисковых запросов в датасет
- Повторение действий, как для для войс-чата (нахождение эмбеддинга и поиск результата)
- Обычно этот вариант занимает не более 4 секунд

#### Теперь про создание датасета:
1. Подготовьте текстовые файлы. Укажите папку с файлами в переменной `folder_path` в `create_dataset.py`.
2. Укажите имя персонажа (`character_name`) и API ключ (`network_tools_api`). Про цены на API и как получить ключ: [тык](https://github.com/Badim41/network_tools?tab=readme-ov-file#цена).
3. Если имена файлов соответствуют темам в них, установите `segmented_input` на `True`
4. Запустите скрипт:
   ```bash
   python dataset/create_dataset.py
   ```

Процесс состоит из трёх этапов:
- **Форматирование**: Текст преобразуется в формат "вопрос-ответ" с использованием API.
- **Сортировка**: Вопросы и ответы сортируются по темам (если `segmented_input=False`).
- **Конвертация в JSON**: Итоговый датасет сохраняется в формате JSON.


#### Поиск сообщений в дискорде для создания датасета
Вначале нужно спарсить, а потом обработать сообщения. Для этого нужно запустить `ds_message_parser.py`, а потом `ds_message_format.py` 
#### ds_message_parser.py
- Укажите `author_id`, `guild_id`, токен Discord.
- После обработки появится 2 файла: `{author_id}_raw.json`, `{author_id}_dialogues.json`.

#### ds_message_format.py
- После обработки появится 2 файла: `formatted-dataset-{character_name}-2.txt`, `dataset_json/{character_name}-2.json`.
- Код также обрабатывает изображения, заменяет `<@user_id>` на имена пользователей.

- Убедитесь, что токен Discord действителен и имеет права на чтение сообщений.
- Для больших объемов данных настройте лимиты в `messages_search` (параметр `limit`).
- Вы можете использовать `formatted_dataset` для обработки в create_dataset.py
- Чтобы убрать обработку изображений в сообщениях, замените `elif message["author_id"] == author_id and i == 0:` на `elif False:` в 90 строке
- Рекомендуется вручную убрать лишние вопросы и ответы в файлах датасета

## Использование

### Голосовой чат + текстовый чат

1. Запустите основной скрипт:
   ```bash
   python main.py
   ```
2. Откройте дискорд с другим аккаунтов в браузере. 'devices_output' из 'secret.py' укажите как микрофон, а '
   device_input' как динамики.

- То есть по умолчанию:
    - "Устройство Ввода": Cable-B-Output
    - "Устройство вывода:" Cable-A-input
3. Зайдите со второго аккаунта в войс-чат
4. Говорите в микрофон в войс-чате или вводите текст — бот обработает запрос и ответит через виртуальный динамик или текстовым
   сообщением.

#### Примечания по войс-чату

- Бот распознает речь, пока вы не остановитесь (должна быть пауза в 1 секунду)
- Генерация речи занимает 9-14 секунд. Если в течение этого времени что-то сказать, то он завершит прошлый запрос и начнёт новый
- Если перебивать бота в течении 3 секунд, то он замолчит.

### Только текстовый чат

1. Запустите скрипт:
   ```bash
   python ds_user.py
   ```
2. Напишите в лс или в обрабатываемый чат боту и он ответит

## Примечания

- Для улучшения качества распознавания русской речи рекомендуется использовать Google Speech Recognition.
- Модель `hailuo TTS (turbo)` обеспечивает быструю и качественную генерацию речи.
