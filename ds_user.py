import asyncio

from discord_user.types import DiscordMessage, PresenceStatus, EventType

import secret
from base_classes import discord_client, event_manager, sql_database, embedding_tools, network_client
from base_logger import Logs
from event_manager import EventTypeForManager
from functions import format_messages, save_answer_to_history
from tts_tools import tts_audio_with_play

activity = secret.activity

system_prompt = secret.system_prompt
character_name = secret.character_name

chat_gpt_model = secret.chat_gpt_model
internet_access = secret.internet_access
max_length_history = secret.max_length_history

reply_on_every_message = secret.reply_on_every_message
handling_chat_ids = secret.handling_chat_ids
say_greeting_text = secret.say_greeting_text

speed = secret.tts_speed
lang = secret.tts_lang
voice_id = secret.voice_id
model_id = secret.tts_model

logger = Logs(warnings=True, name="ds-user")

current_voice_chat_id = None
current_voice_chat_members = []
greeted_users = []  # пользователи, с которыми приветствовался бот


def get_nick(message: DiscordMessage):
    nickname = message._data.get('member', {}).get('nick')
    if not nickname:
        nickname = message.author.global_name
        logger.logging(f"Не найден ник для: {nickname} <@{message.author.id}>")
    return nickname


@discord_client.message_handler
async def on_message(message: DiscordMessage):
    global current_voice_chat_id
    if message.channel_id not in [current_voice_chat_id] + handling_chat_ids:
        return

    text = message.text
    response_text = None
    nickname = get_nick(message)

    logger.logging(f"Got message. {nickname}: {text}")

    # Получаем контекст
    if message.channel_id == current_voice_chat_id:
        context = EventTypeForManager.voice_chat_text_messages
    else:
        context = None

    chat_history = sql_database.get('chat_history_chat', [])
    formatted_chat_history = format_messages(chat_history, max_length=max_length_history)

    # 1. пинг пользователя
    user_ping = discord_client.info.user_id in message.mentions
    if message.referenced_message:
        user_ping = user_ping or discord_client.info.user_id == message.referenced_message.author.id
    # 2. @everyone @here
    mention_here = message.mention_everyone
    # 3. любое имя персонажа в сообщении
    name_mention = any(
        obj.lower() in text.lower() for obj in [
            discord_client.info.global_name,
            discord_client.info.username,
            discord_client.info.user_id,
            character_name
        ]
    )
    print("user_ping", user_ping, "mention", mention_here, "name", name_mention)
    if (user_ping or mention_here or name_mention or reply_on_every_message) and text and text.strip():
        memories_character = embedding_tools.get_memories(text)

        # Без включения событий!
        full_prompt = (
            f"# Задача\n"
            f"{system_prompt}\n\n"  # Ты полезный ассистент...
            f"{memories_character}\n\n"  # '# Память персонажа\n...'
            f"# История сообщений\n"
            f"{formatted_chat_history}\n\n"  # '# Nickname\nText\n# Char\nText'
            f"# Текущий запрос {nickname}\n"
            f"{text}"
        )

        answer_gpt = await asyncio.to_thread(
            network_client.chatgpt_api,
            prompt=full_prompt,
            model=chat_gpt_model,
            internet_access=internet_access
        )
        response_text = answer_gpt.response.text

        await discord_client.send_message(message.channel_id, response_text, file_path=None)

    elif not text is None:
        logger.logging(f"Skip reply: {text[:20]}")

    # сохраняем в память
    if text:
        if context:
            event_manager.create_event(
                f"{nickname}: {text}",
                context=context,
                static=False
            )
        elif response_text:
            chat_history = save_answer_to_history(
                chat_history=chat_history,
                prompt=text,
                user_nickname=nickname,
                answer=response_text,
                character_nickname=character_name
            )
            sql_database['chat_history_voice'] = chat_history
        else:
            logger.logging(f"Пропуск сохранения ответа: {message.text} ({nickname}, <@{message.author.id}>)")


@discord_client.on_start
async def on_start():
    print("self.info", bool(discord_client.info))
    # Установка активности пользователя
    await discord_client.change_activity(activity=activity, status=PresenceStatus.IDLE)


@discord_client.event_handler(EventType.SESSIONS_REPLACE)
async def on_session_replace(data):
    # Установка активности пользователя
    await discord_client.change_activity(activity=activity, status=PresenceStatus.IDLE)


@discord_client.voice_status_handler
async def on_voice_status_update(data):
    """
    {
        "member": {
            "user": {
                ...
                "id": "989871157702447164",
                "display_name": "NAME"
            },
            "joined_at": "2024-10-20T12:35:18.463000+00:00"
        },
        "guild_id": "1012237304028467293",
        "channel_id": "1356152765784522823"
    }
    """
    global current_voice_chat_id
    # Бот
    if data['member']['user']['bot'] and data['channel_id'] == current_voice_chat_id:
        logger.logging("В войс-чат зашёл бот. Рекомендую замьютить его")
        return

    # {'user_id': '544816254435983360', 'channel_id': '1099481964253294723'}
    # print(f"voice update: {data}")
    if data['user_id'] == discord_client.info.user_id:
        if current_voice_chat_id != data['channel_id']:
            current_voice_chat_id = data['channel_id']
            logger.logging("Изменён Voice chat id:", current_voice_chat_id)
    else:  # Зашёл/вышел из войса
        all_user_ids_in_voice = [user['id'] for user in current_voice_chat_members]
        current_user = data['member']['user']

        # Вышел. channel_id - None
        if current_user['id'] in all_user_ids_in_voice and not data['channel_id']:
            ind = all_user_ids_in_voice.index(current_user['id'])
            current_voice_chat_members.remove(ind)

            # Удаление текущего ивента о пользователях
            event_manager.remove_events(EventTypeForManager.current_voice_chat_members)

            usernames_in_voice_chat = [user['display_name'] for user in current_voice_chat_members]
            usernames_in_voice_chat = '\n'.join(usernames_in_voice_chat)

            # Добавление нового ивента о пользователях
            event_manager.create_event(
                usernames_in_voice_chat,
                context=EventTypeForManager.current_voice_chat_members,
                static=True
            )
            event_manager.create_event(
                f"Вышел: {current_user['display_name']}",
                context=EventTypeForManager.voice_chat_joins,
                static=False
            )
        elif data['channel_id'] == current_voice_chat_id and current_user['id'] not in all_user_ids_in_voice:
            current_voice_chat_members.append(current_user)

            # Удаление текущего ивента о пользователях
            event_manager.remove_events(EventTypeForManager.current_voice_chat_members)

            usernames_in_voice_chat = [user['display_name'] for user in current_voice_chat_members]
            usernames_in_voice_chat = '\n'.join(usernames_in_voice_chat)

            # Добавление нового ивента о пользователях
            event_manager.create_event(
                usernames_in_voice_chat,
                context=EventTypeForManager.current_voice_chat_members,
                static=True
            )
            event_manager.create_event(
                f"Зашёл: {current_user['display_name']}",
                context=EventTypeForManager.voice_chat_joins,
                static=False
            )
            if current_user['id'] not in greeted_users and say_greeting_text:
                greeted_users.append(current_user['id'])
                tts_audio_with_play(
                    text=f"Привет {current_user['display_name']}!",
                    speed=speed,
                    lang=lang,
                    voice_id=voice_id,
                    model_id=model_id
                )


def activate_handlers():
    logger.logging("Handlers activated")
