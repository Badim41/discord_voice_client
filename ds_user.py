import asyncio
import re
import time
import traceback

from discord_user.types import DiscordMessage, PresenceStatus, EventType
from network_tools import ImageModels, AspectRatio

import secret
from base_classes import discord_client, event_manager, sql_database_discord, embedding_tools, network_client
from base_logger import Logs, Color
from event_manager import EventTypeForManager
from functions import format_messages, save_answer_to_history, convert_answer_to_json, remove_emojis, \
    download_image_path_from_message
from tts_tools import tts_audio_with_play

activity = secret.activity

system_prompt = secret.system_prompt
answer_json_examples = secret.answer_json_examples
answer_json_format = secret.answer_json_format
character_name = secret.character_name

chat_gpt_model = secret.chat_gpt_model
internet_access = secret.internet_access

reply_on_every_message = secret.reply_on_every_message
handling_chat_ids = secret.handling_chat_ids
handling_guild_ids = secret.handling_guild_ids
say_greeting_text = secret.say_greeting_text
max_reactions = secret.max_reactions
send_message_limit = secret.send_message_limit
message_delay = secret.message_delay

speed = secret.tts_speed
lang = secret.tts_lang
voice_id = secret.voice_id
model_id = secret.tts_model

logger = Logs(warnings=True, name="ds-user")

current_voice_chat_id = None
current_voice_chat_members = []
greeted_users = []  # пользователи, с которыми приветствовался бот

message_counts = {"all": {"count": 0, "last_time": 0.0}}


def is_limit_reached(limit_keys: list[str], current_time: float) -> bool:
    """Проверяет, достигнут ли лимит для списка ключей (например, [guild_id, channel_id]) и 'all'.
    Возвращает True, если любой лимит достигнут, иначе False. Увеличивает счетчики, если лимиты не достигнуты."""
    # Проверка общего лимита "all" (всегда выполняется, если задан)
    print(f"Сообщение отправлено: {limit_keys}")
    print("message_counts", message_counts)
    if "all" in send_message_limit:
        if "all" not in message_counts:
            message_counts["all"] = {"count": 0, "last_time": 0}
        limit = send_message_limit["all"]
        time_diff = current_time - message_counts["all"]["last_time"]
        if time_diff < limit["time"]:
            if message_counts["all"]["count"] >= limit["count"]:
                return True  # Превышен общий лимит
        else:
            # Сбрасываем только если время вышло
            message_counts["all"]["count"] = 0
            message_counts["all"]["last_time"] = current_time

    # Проверка лимитов для каждого ключа в списке
    for limit_key in limit_keys:
        # Определяем лимит: конкретный, если есть, иначе "default"
        limit = send_message_limit.get(limit_key, send_message_limit.get("default"))

        # Если лимита нет, пропускаем проверку
        if limit is None:
            continue

        # Если ключ еще не в message_counts, создаем его
        if limit_key not in message_counts:
            message_counts[limit_key] = {"count": 0, "last_time": 0}

        # Проверка времени и лимита для конкретного ключа
        time_diff = current_time - message_counts[limit_key]["last_time"]
        if time_diff < limit["time"]:
            if message_counts[limit_key]["count"] >= limit["count"]:
                return True  # Лимит достигнут
        else:
            # Сбрасываем только если время вышло
            message_counts[limit_key]["count"] = 0
            message_counts[limit_key]["last_time"] = current_time

    # Увеличиваем счетчики, если лимиты не достигнуты
    if "all" in send_message_limit:
        message_counts["all"]["count"] += 1
    for limit_key in limit_keys:
        limit = send_message_limit.get(limit_key, send_message_limit.get("default"))
        if limit is not None:  # Увеличиваем только если лимит задан
            message_counts[limit_key]["count"] += 1

    return False


def get_nick(message: DiscordMessage):
    return message.author.global_name
    # nickname = message._data.get('member', {}).get('nick')
    # if not nickname:
    #     nickname = message.author.global_name
    #     logger.logging(f"Не найден ник для: {nickname} <@{message.author.id}>")
    # return nickname


async def on_message_thread(message: DiscordMessage):
    text = message.text
    nickname = get_nick(message)
    # замена всех <@...> на имена известных пользователей. Включая своё имя, но подставив в него character_name
    known_users = sql_database_discord.get("known_users", {})
    known_users[str(message.author.id)] = nickname
    sql_database_discord["known_users"] = known_users

    mentions = re.findall(r"<@(\d+)>", text)

    for mention in mentions:
        user_id = str(mention)
        # Заменяем упоминание твоего имени
        if user_id == discord_client.info.user_id:
            text = text.replace(f"<@{mention}>", character_name)
        elif user_id in known_users:
            # Заменяем на имя известного пользователя
            nickname_this = known_users[user_id]
            text = text.replace(f"<@{mention}>", nickname_this)
        # Если пользователя нет в known_users, можно оставить оригинальное упоминание

    response_text = None
    image_input = None

    logger.logging(f"Got message. {nickname}: {text}")

    # Получаем контекст
    if message.channel_id == current_voice_chat_id:
        context = EventTypeForManager.voice_chat_text_messages
    else:
        context = None

    chat_history_key = f'chat_history_{message.channel_id}'

    if '/clear' in message.text:
        sql_database_discord[chat_history_key] = []
        logger.logging(f"История очищена для: {chat_history_key}")
        return

    chat_history = sql_database_discord.get(chat_history_key, [])

    # Проверка упоминаний
    user_ping = False
    if message.referenced_message:
        user_ping = discord_client.info.user_id == message.referenced_message.author.id
    # mention_here = message.mention_everyone
    name_mention = any(
        obj.lower() in text.lower() for obj in [
            discord_client.info.global_name,
            discord_client.info.username,
            discord_client.info.user_id,
            character_name
        ]
    )

    if user_ping or name_mention or reply_on_every_message or not message.guild_id:
        # Проверка лимита сообщений
        current_time = time.time()
        guild_id = str(message.guild_id)
        channel_id = str(message.channel_id)
        if is_limit_reached([guild_id, channel_id], current_time):
            logger.logging(f"Достигнут лимит на сообщения: {[guild_id, channel_id]}", color=Color.PURPLE)
            await discord_client.set_reaction(
                chat_id=message.channel_id,
                message_id=message.message_id,
                reaction="⏳"
            )
        else:
            try:
                asyncio.ensure_future(discord_client.send_typing(message.channel_id))

                formatted_chat_history = format_messages(chat_history)

                image_input = await asyncio.to_thread(download_image_path_from_message, message)
                print("img input", image_input)

                try:
                    memories_character = embedding_tools.get_memories(
                        text,
                        deepsearch=True,
                        file_path=image_input,
                        formatted_chat_history=formatted_chat_history,
                        max_results=10
                    )
                except Exception as e:
                    logger.logging(f"Error in memories_character: {e}")
                    memories_character = ""

                prompt_words = str(text).count(" ")
                if image_input:
                    prompt_words += 3
                if prompt_words > 50:
                    num_sentences = "3-5 предложение"
                elif prompt_words > 15:
                    num_sentences = "2-3 предложение"
                elif prompt_words > 5:
                    num_sentences = "2 предложение"
                else:
                    num_sentences = "1-2 односложное предложение"

                # Без включения событий!
                full_prompt = (
                    f"# Задача\n"
                    f"{system_prompt}\n\n"  # Ты полезный ассистент...
                    f"{memories_character}\n\n"  # '# Память персонажа\n...'
                    f"# Формат выводи\n{answer_json_format}\n\n"  # для Json
                    f"# Примеры вывода\n{answer_json_examples}\n\n"  # для Json
                    f"# История сообщений\n"
                    f"{formatted_chat_history}\n\n"  # '# Nickname\nText\n# Char\nText'
                    f"# Текущий запрос {nickname}\n"
                    f"{text}"
                ).replace("NUM_SENTENCES", num_sentences, 1)

                answer_gpt = await asyncio.to_thread(
                    network_client.chatgpt_api,
                    prompt=full_prompt,
                    model=chat_gpt_model,
                    internet_access=internet_access,
                    file_path=image_input
                )

                converted, json_answer = convert_answer_to_json(
                    answer_gpt.response.text,
                    end_symbol="]",
                    start_symbol="[",
                    keys=[]
                )

                send_reactions = 0
                send_messages = 0

                # Обработка JSON-ответа
                for n_action, action in enumerate(json_answer):
                    if action.get("event_type") == "write":
                        # Отправка сообщения

                        # Найти кому ответить
                        reply_to = action.get("reply_to", "")
                        reply_message = None
                        if reply_to.lower() == nickname.lower() or not reply_to:
                            reply_message = message
                        else:
                            history_messages = discord_client.get_messages(message.channel_id)
                            history_messages = reversed(history_messages)
                            for history_message in history_messages:
                                if reply_to.lower() == get_nick(history_message).lower():
                                    reply_message = history_messages
                                    break

                        message_text = remove_emojis(action.get("text", ""))
                        image_desc = action.get("image")

                        if image_desc:
                            # Генерация и отправка картинки
                            image_prompt = image_desc
                            for image_group in network_client.image_generate_api(
                                    [ImageModels.gemini],
                                    image_prompt,
                                    AspectRatio.ratio_3x2,
                                    send_url=True
                            ):
                                if image_group and len(image_group) > 0:
                                    try:
                                        await discord_client.send_message(
                                            chat_id=message.channel_id,
                                            text=message_text + f"[̤̮]({image_group[0]})",
                                            reply_message=reply_message if send_messages == 0 else None
                                        )
                                    except Exception as e:  # если история чата скрыта, будет ошибка
                                        logger.logging(f"Error in send 1: {e}")
                                        await discord_client.send_message(
                                            chat_id=message.channel_id,
                                            text=message_text + f"[̤̮]({image_group[0]})"
                                        )
                        else:
                            # Отправка текстового сообщения
                            try:  # если история чата скрыта, будет ошибка
                                await discord_client.send_message(
                                    chat_id=message.channel_id,
                                    text=message_text,
                                    reply_message=reply_message if send_messages == 0 else None
                                )
                            except Exception as e:
                                logger.logging(f"Error in send 1: {e}")
                                await discord_client.send_message(
                                    chat_id=message.channel_id,
                                    text=message_text
                                )
                        send_messages += 1
                        if n_action != len(json_answer) - 1:  # не последний ивент
                            await asyncio.sleep(message_delay)
                        response_text = message_text if not response_text else f"{response_text}\n{message_text}"
                        if image_desc:
                            response_text += f"\n<image>{image_desc}</image>"

                    elif action.get("event_type") == "reaction":
                        # Установка реакции
                        reaction = action.get("reaction")
                        if reaction and send_reactions < max_reactions:
                            await discord_client.set_reaction(
                                chat_id=message.channel_id,
                                message_id=message.message_id,
                                reaction=reaction
                            )
                            send_reactions += 1
            except Exception as e:
                logger.logging(f"CRITICAL ERROR IN DS_USER: {traceback.format_exc()}")
    elif text is not None:
        logger.logging(f"Skip reply: {text[:20]}")

    # Сохранение в память
    if context and text:
        event_manager.create_event(
            f"{nickname}: {text}",
            context=context,
            static=False
        )
    elif image_input or text:
        chat_history = save_answer_to_history(
            chat_history=chat_history,
            prompt=text,
            user_nickname=nickname,
            answer=response_text,
            character_nickname=character_name
        )
        sql_database_discord[chat_history_key] = chat_history
    else:
        logger.logging(f"Пропуск сохранения ответа: {message.text} ({nickname}, <@{message.author.id}>)")

    logger.logging(f"end generate: {message.channel_id}")


@discord_client.message_handler
async def on_message(message: DiscordMessage):
    global current_voice_chat_id
    in_handle_channel = str(message.channel_id) in [current_voice_chat_id] + handling_chat_ids
    in_handle_guild = str(message.guild_id) in handling_guild_ids
    # print("in_handle_channel", in_handle_channel)
    # print("in_handle_guild", in_handle_guild)
    if message.author.id == discord_client.info.user_id or (not in_handle_channel and not in_handle_guild):
        return
    asyncio.ensure_future(on_message_thread(message))


@discord_client.on_start
async def on_start():
    # Установка активности пользователя
    await discord_client.change_activity(activity=activity, status=PresenceStatus.ONLINE)


@discord_client.event_handler(EventType.SESSIONS_REPLACE)
async def on_session_replace(data):
    # Установка активности пользователя
    await discord_client.change_activity(activity=activity, status=PresenceStatus.ONLINE)


@discord_client.voice_status_handler
async def on_voice_status_update(data):
    asyncio.ensure_future(on_voice_status_update_wrapped(data))


async def on_voice_status_update_wrapped(data):
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
        if current_voice_chat_id != data['channel_id'] and data['channel_id']:
            current_voice_chat_id = data['channel_id']
            logger.logging("Изменён Voice chat id:", current_voice_chat_id)
    else:  # Зашёл/вышел из войса
        all_user_ids_in_voice = [user['id'] for user in current_voice_chat_members]
        current_user = data['member']['user']

        # Вышел. channel_id - None
        if current_user['id'] in all_user_ids_in_voice and not data['channel_id']:
            current_voice_chat_members.remove(current_user)

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
        elif current_voice_chat_id and data['channel_id'] == current_voice_chat_id and current_user[
            'id'] not in all_user_ids_in_voice:
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
                    model_id=model_id,
                    stop_event=None
                )


def activate_handlers():
    logger.logging("Handlers activated")


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(discord_client.start_polling())
