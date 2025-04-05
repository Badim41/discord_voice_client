import json
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import secret


def messages_search(author_id, guild_id, limit=float("inf")):
    url = f"https://discord.com/api/v9/guilds/{guild_id}/messages/search"
    payload = ""
    headers = {
        "Authorization": secret.auth_token_discord
    }
    querystring = {"author_id": author_id}

    response = req_session.request("GET", url, data=payload, headers=headers, params=querystring, proxies=proxies)
    response_json = response.json()

    total_results = response_json['total_results']
    print(f"Всего сообщений: {total_results}")

    messages = []

    for i in range((total_results - 1) // 25 + 1):
        querystring["offset"] = i * 25

        time.sleep(2)
        if i * 25 > limit:
            break

        response = req_session.request("GET", url, data=payload, headers=headers, params=querystring, proxies=proxies)
        response_json = response.json()
        messages.extend(response_json.get("messages", []))

    return messages


def get_messages_around(channel_id, message_id, limit=50) -> list:
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    querystring = {"limit": str(limit), "around": message_id}
    headers = {
        "authorization": secret.auth_token_discord
    }

    response = req_session.request("GET", url, headers=headers, params=querystring, proxies=proxies)
    return response.json()


def process_dialogue(main_message, author_id):
    channel_id = main_message['channel_id']
    message_id = main_message['id']

    # Получаем 50 сообщений вокруг целевого сообщения
    messages_around = get_messages_around(channel_id, message_id)

    # Сортируем сообщения по времени (от старых к новым)
    messages_around.sort(key=lambda x: x['timestamp'], reverse=True)

    dialogue = []
    target_message_index = None

    # Находим индекс целевого сообщения
    for i, msg in enumerate(messages_around):
        if msg['id'] == message_id:
            target_message_index = i
            break

    if target_message_index is None:
        return []

    # Добавляем целевое сообщение
    dialogue.append({
        "id": main_message['id'],
        "content": main_message['content'],
        "timestamp": main_message['timestamp'],
        "author_id": main_message['author']['id'],
        "attachments": main_message.get('attachments', [])
    })

    # Считаем сообщения других пользователей после целевого
    other_messages_count = 0

    # Добавляем сообщения после целевого (максимум 10 от других пользователей)
    for msg in messages_around[target_message_index + 1:]:
        if other_messages_count >= 10:
            break

        dialogue.append({
            "id": msg['id'],
            "content": msg['content'],
            "timestamp": msg['timestamp'],
            "author_id": msg['author']['id'],
            "attachments": msg.get('attachments', [])
        })

        if msg['author']['id'] != author_id:
            other_messages_count += 1

    return dialogue


def save_dialogues(messages, author_id):
    flat_messages = [item for sublist in messages for item in sublist]
    dialogues = []

    # Обрабатываем каждое сообщение пользователя
    processed_message_ids = set()

    for message in flat_messages:
        if message['author']['id'] == author_id and message['id'] not in processed_message_ids:
            dialogue = process_dialogue(message, author_id)
            if dialogue:
                dialogues.append(dialogue)
                # Помечаем все сообщения пользователя из этого диалога как обработанные
                for msg in dialogue:
                    if msg['author_id'] == author_id:
                        processed_message_ids.add(msg['id'])

    return dialogues


req_session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
req_session.mount('http://', HTTPAdapter(max_retries=retries))
req_session.mount('https://', HTTPAdapter(max_retries=retries))

proxies = secret.discord_proxies

author_id = "USER_ID"
guild_id = "GUILD_ID"

# Получаем все сообщения пользователя
result_messages = messages_search(author_id=author_id, guild_id=guild_id)
# result_messages = result_messages[:2]
# Сохраняем необработанные сообщения
with open(f"{author_id}_raw.json", "w", encoding="utf-8") as output_file:
    json.dump(result_messages, output_file, ensure_ascii=False, indent=4)

# Обрабатываем диалоги
dialogues = save_dialogues(result_messages, author_id)

# Сохраняем обработанные диалоги
with open(f"{author_id}_dialogues.json", "w", encoding="utf-8") as output_file:
    json.dump(dialogues, output_file, ensure_ascii=False, indent=4)

# Сохраняем обработанные диалоги
with open(f"{author_id}_dialogues.json", "r", encoding="utf-8") as json_file:
    dialogues = json.load(json_file)
dialogues = dialogues[:3]
print(f"Сохранено {len(dialogues)} диалогов")
for i, dialogue in enumerate(dialogues):
    dialogue = reversed(dialogue)
    print(f"\nДиалог {i + 1}:")
    for msg in dialogue:
        print(f"[{msg['timestamp']}] "
              f"{'Author' if msg['author_id'] == author_id else 'Other'}: "
              f"{msg['content']}")
