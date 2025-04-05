import hashlib
import os
import json
import re
from functools import lru_cache

import requests
from network_tools import NetworkToolsAPI, GptModels
from network_tools.sql_storage import DictSQL
import secret


from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dataset_funcs import get_hash, download_image_path_from_message, parse_to_json

# Настройки
DOWNLOAD_DIR = "images"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

network_tools_api = secret.network_tools_api
network_client = NetworkToolsAPI(api_key=network_tools_api)
model = GptModels.gpt_4o_mini
prompt = """
# Task
Imagine you have an image, and you need to provide a description

# Format
<image> {description} <image/> 

Where:  
- `{image}` — a description of the image.

## User's Request  

What text is written on the image?

## Example Model Response  

```
<image> The image shows a woman in a red dress sitting at a table in a cafe with a cup of coffee. Other visitors and the interior with plants are visible in the background. <image/>  
```
"""

chat_history = []
author_id = "USER_ID"
character_name = "CHAR_NAME"

# Выходные файлы
formatted_dataset = f"formatted-dataset-{character_name}-2.txt"
sorted_dataset = f"dataset-sorted-{character_name}-2.txt"
sorted_dataset_json = f"dataset_json/{character_name}-2.json"

# Загрузка JSON
with open(f"{author_id}_dialogues.json", "r", encoding="utf-8") as f:
    dialogues = json.load(f)

seen_descriptions = DictSQL("attachments")

# Проход по диалогам
for dialogue in dialogues:
    for message in dialogue:
        for i, attachment in enumerate(message.get("attachments", [])):
            url = attachment["url"]
            filename = get_hash(url)

            description = None
            if filename in seen_descriptions:
                description = seen_descriptions[filename]
            elif message["author_id"] == author_id and i == 0:
                file_path = download_image_path_from_message(filename, message)

            # Получение описания
            try:
                if not description:
                    response = network_client.chatgpt_api(prompt, model=model, chat_history=chat_history, file_path=file_path)
                    description = response.response.text.strip()
                print("description", description)
                if description:
                    seen_descriptions[filename] = description
                    message["content"] += f"\n\n{description}"
            except Exception as e:
                print(f"Ошибка при описании {filename}: {e}")

# Сохраняем обновлённый JSON
with open("updated_dialogues.json", "w", encoding="utf-8") as f:
    json.dump(dialogues, f, ensure_ascii=False, indent=4)

with open(f"updated_dialogues.json", "r", encoding="utf-8") as json_file:
    updated_dialogues = json.load(json_file)


MAX_CHUNK_SIZE = 7000
chunks = []
data_memory = []
current_chunk = ""

for i, dialogue in enumerate(updated_dialogues):
    dialogue = list(reversed(dialogue))  # преобразуем в список, т.к. reversed возвращает итератор
    dialogue_text = f"\nДиалог {i + 1}:\n"
    for msg in dialogue:
        role = character_name if msg['author_id'] == author_id else f'<@{msg["author_id"]}>'
        dialogue_text += f"{role}: {msg['content']}"

    # Если добавление следующего диалога превышает лимит — сохранить текущий и начать новый
    if len(current_chunk) + len(dialogue_text) > MAX_CHUNK_SIZE:
        chunks.append(current_chunk.strip())
        data_memory.append(f"Сообщения в дискорд за ~{msg['timestamp'][:10]}\n")
        current_chunk = dialogue_text
    else:
        current_chunk += dialogue_text

# Добавить последний кусок, если он не пуст
if current_chunk.strip():
    chunks.append(current_chunk.strip())
    data_memory.append(f"Сообщения в дискорд за ~{msg['timestamp'][:10]}\n")

for chunk in chunks:
    print(f"Длина куска \"{chunk[:20]} ... {chunk[-20:]}\": {len(chunk)}")

print(f'Количество кусков текста: {len(chunks)}')

input("Press Enter to continue")
print("Part 1. Форматирование.")

for i, text_chunk in enumerate(chunks):
    if i < 188:
        continue
    extra_text = f"Ты читаешь файл сообщения в дискорд\n\n"
    prompt = ("# Задача\n\n"
              f"Выведи информацию о {character_name} в формате вопрос-ответ. Нужно уделять внимания личностям на сервере, и другим неочевидным аспектам сервера. Если какие-то люди ОЧЕНЬ СИЛЬНО выделяются, можешь прям записать их <@...>\n\n"
              f"{extra_text}"
              "# Пример\n"
              "## Вопрос\n"
              "Как тебя зовут?\n"
              "## Ответ\n"
              f"Меня зовут {character_name}\n\n"
              "# Информация\n\n")
    answer = network_client.chatgpt_api(prompt=prompt + text_chunk, model=GptModels.chatgpt_4o)
    print(f"got answer {i + 1}: {answer.response.text[:20]} ...")
    with open(formatted_dataset, "a", encoding="utf-8", errors="ignore") as writer:
        text = answer.response.text.replace("## Вопрос", "### Вопрос").replace("## Ответ", "### Ответ")
        text = f"## {data_memory[i]}\n\n{text}\n"
        writer.write(text)

input("Press Enter to continue")
print("Part 3. Форматирование в JSON")

with open(formatted_dataset, 'r', encoding='utf-8') as file:
    text = file.read()
result = parse_to_json(text)
with open(sorted_dataset_json, 'w', encoding='utf-8') as file:
    json.dump(result, file, ensure_ascii=False, indent=4)

print(f"Датасет 'вопрос-ответ' сохранён: {sorted_dataset_json}")

req_session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
req_session.mount('http://', HTTPAdapter(max_retries=retries))
req_session.mount('https://', HTTPAdapter(max_retries=retries))

@lru_cache(10**10)
def get_name(user_id):
    url = f"https://discord.com/api/v9/users/{user_id}/profile"

    querystring = {"type": "panel", "with_mutual_guilds": "true", "with_mutual_friends": "true",
                   "with_mutual_friends_count": "true"}

    payload = ""
    headers = {
        "accept": "*/*",
        "accept-language": "ru,en;q=0.9",
        "authorization": secret.auth_token_discord,
    }

    response = req_session.request("GET", url, data=payload, headers=headers, params=querystring)
    json_data = response.json()
    print(json_data)
    global_name = json_data.get("user", {}).get("global_name")
    if global_name:
        return global_name
    username = json_data.get("user", {}).get("username")
    if username:
        return username
    return f"<@{user_id}>"

def replace_mentions_in_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for section in data:
        items = data[section]
        if isinstance(items, list):
            for item in items:
                for key, text in item.items():
                    matches = re.findall(r"<@(\d+)>", text)
                    for user_id in matches:
                        name = get_name(user_id)
                        text = text.replace(f"<@{user_id}>", f"'{name}'")
                    item[key] = text

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

replace_mentions_in_json(sorted_dataset_json)

print(f"Все упоминания изменены. Датасет 'вопрос-ответ' сохранён: {sorted_dataset_json}")