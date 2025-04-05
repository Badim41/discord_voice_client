import hashlib
import json
import random
import re
import string
import subprocess
import uuid

import magic
import requests
from PIL import Image
from discord_user.types import DiscordMessage
from discord_user.utils.re_str import extract_discord_emojis

import secret
from base_logger import Logs

logger = Logs(warnings=True, name="funcs")
discord_proxies = secret.discord_proxies


def format_messages(
        messages,
        max_length: int = secret.max_length_history,
        max_length_history_messages: int = secret.max_length_history_messages
):
    formatted_messages = []
    current_length = 0

    # Обрабатываем сообщения в обратном порядке для приоритета новым,
    # но потом развернем для сохранения исходного порядка
    messages = list(reversed(messages))[-max_length_history_messages:]
    for message in messages:
        role = message.get('role', '')
        content = message.get('content', '')

        # Обрабатываем содержимое
        content_str = ''
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get('text', '')
                    content_str += text + "\n"
        else:
            content_str = str(content) + "\n"

        # Формируем сообщение без лишних префиксов для строк контента
        formatted_message = f"{role}: {content_str.strip()}\n"

        # Проверяем длину с учетом max_length
        if max_length is not None:
            if current_length + len(formatted_message) > max_length:
                # Если сообщение не помещается, обрезаем его
                remaining_length = max_length - current_length
                if remaining_length > 0:
                    formatted_messages.append(formatted_message[:remaining_length])
                break
            current_length += len(formatted_message)

        formatted_messages.append(formatted_message)

    # Возвращаем сообщения в исходном порядке
    return "\n".join(reversed(formatted_messages))


def save_answer_to_history(chat_history, prompt, user_nickname, answer, character_nickname):
    if user_nickname and prompt:
        chat_history.append({"role": user_nickname, "content": prompt})
    if character_nickname and answer:
        chat_history.append({"role": character_nickname, "content": answer})
    return chat_history


import datetime


class Time_Count:
    def __init__(self):
        self.start_time = datetime.datetime.now()

    def count_time(self, ignore_error=True, return_ms=False):
        end_time = datetime.datetime.now()
        spent_time = str(end_time - self.start_time)
        # убираем миллисекунды
        if not return_ms:
            spent_time = spent_time[:spent_time.find(".")]
        if not "0:00:00" in str(spent_time) or ignore_error:
            return spent_time


def random_string(length=8, seed=None, input_str=None):
    if not input_str is None:
        # Создаем хэш входной строки
        hash_object = hashlib.sha256(input_str.encode())
        hash_hex = hash_object.hexdigest()
        # Инициализируем генератор случайных чисел на основе хэша
        random.seed(hash_hex)
    elif not seed is None:
        random.seed(seed)
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))


def convert_answer_to_json(answer: str, keys, start_symbol="{", end_symbol="}", attemtp=1) -> [bool, dict]:
    def convert_answer_to_json_2():
        lines = answer.split("\n")
        if start_symbol == "{":
            result_json = {}
            for key in keys:
                for line in lines:
                    if line.startswith(key):
                        line_else = line[len(key) + 1:]
                        if str(line_else).lower().replace(",", "").replace(" ", "") == "true":
                            result_json[key] = True
                        elif str(line_else).lower().replace(",", "").replace(" ", "") == "null":
                            result_json[key] = None
                        elif str(line_else).lower().replace(",", "").replace(" ", "") == "false":
                            result_json[key] = False
                        else:
                            result_json[key] = line_else
                        print("found key", key)
                        break
                else:  # не найден ключ
                    return
            # print("result_json-2", result_json)
            return result_json

    if isinstance(keys, str):
        keys = [keys]

    answer = answer.replace(" ", "").replace(" None", " null").replace(" False", " false").replace(" True", " true")

    if attemtp == 2:
        if start_symbol in answer and end_symbol in answer:
            answer = answer[answer.find(start_symbol):]
            answer = answer[:answer.find(end_symbol) + 1]
        else:
            print("Не json")
            return False, "Не json"
    elif attemtp == 1:
        if start_symbol in answer and end_symbol in answer:
            answer = answer[answer.find(start_symbol):]
            answer = answer[:answer.rfind(end_symbol) + 1]
        else:
            print("Не json")
            return False, "Не json"
    else:
        return False, "ERROR"

    try:
        response = json.loads(answer)
        for key in keys:
            if response.get(key, "NULL_VALUE") == "NULL_VALUE":
                print("Нет ключа")
                return False, "Нет ключа"
        return True, response
    except json.JSONDecodeError as e:
        result_2 = convert_answer_to_json_2()
        if result_2:
            return True, result_2
        print("Error", e)
        return convert_answer_to_json(answer=answer, keys=keys, start_symbol=start_symbol, end_symbol=end_symbol,
                                      attemtp=attemtp + 1)


def remove_emojis(text):
    emoji_pattern = re.compile("["
                               u"\U0001F600-\U0001F64F"  # смайлики эмодзи
                               u"\U0001F300-\U0001F5FF"  # символы и пиктограммы
                               u"\U0001F680-\U0001F6FF"  # символы транспорта и карты
                               u"\U0001F900-\U0001F9FF"  # дополнительные эмодзи
                               u"\U00002702-\U000027B0"  # символы с подсказками
                               u"\U000024C2-\U0001F251"  # дополнительные символы
                               u"\U0001F1E0-\U0001F1FF"  # флаги
                               "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)


def get_mime_type_from_content(file_path):
    try:
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(file_path)
        return mime_type
    except Exception as e:
        logger.logging(f"Error detecting MIME type with python-magic: {e}")
        return None


def download_content(url, output_file, attempts=10):
    for i in range(attempts):
        try:
            response = requests.get(url, stream=True, proxies=discord_proxies)
            response.raise_for_status()

            with open(output_file, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
            # Определяем MIME-тип по содержимому файла
            mime_type = get_mime_type_from_content(output_file)
            return True, mime_type or 'image/NotFound'
        except Exception as e:
            logger.logging(f"Temp error in download: {e}")
    return False, None


def convert_image_to_png(input_file, output_file):
    try:
        with Image.open(input_file) as img:
            img.convert("RGBA").save(output_file, "PNG")
        return True
    except Exception as e:
        logger.logging(f"Error converting image to PNG: {e}")
        return False


def extract_first_frame_from_gif(input_file, output_file):
    try:
        with Image.open(input_file) as img:
            # Extract the first frame from the GIF
            img.seek(0)
            img.save(output_file, "PNG")
        return True
    except Exception as e:
        logger.logging(f"Error extracting frame from GIF: {e}")
        return False


def extract_first_frame_from_video(video_url, output_file):
    try:
        # Build the ffmpeg command to extract the first frame from the video
        command = [
            'ffmpeg',
            '-i', video_url,  # Input file (video URL or path)
            '-ss', '00:00:01',  # Seek to 1 second to ensure we get a frame
            '-vframes', '1',  # Extract only 1 frame
            output_file  # Output file (image path)
        ]

        # Execute the command
        subprocess.run(command, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.logging(f"Error extracting frame from video: {e}")
        return False


def download_image_path_from_message(message: DiscordMessage):
    emojies_in_message = extract_discord_emojis(message.text)

    attachment_urls = []

    if message.sticker_items:
        print("sticker_items")
        attachment_urls = [message.sticker_items[0].get_url()]
    elif emojies_in_message:
        print("emojies_in_message")
        attachment_urls = [emoji.get_url() for emoji in emojies_in_message]
    elif message.attachments:
        print("attachments")
        attachment_urls = [attachment['url'] for attachment in message.attachments]
    elif message.embeds:
        print("embeds")
        for embed in message.embeds:
            if 'video' in embed and 'proxy_url' in embed['video']:
                attachment_urls.append(embed['video']['proxy_url'])
            elif 'thumbnail' in embed and 'proxy_url' in embed['thumbnail']:
                attachment_urls.append(embed['thumbnail']['proxy_url'])
            else:
                logger.logging(f"Cant get media from embed: {embed}")

    print("attachment_urls", attachment_urls)
    for url in attachment_urls:
        # Download the content
        temp_output_path = f"images/{uuid.uuid4()}.tmp"
        success, mime_type = download_content(url, temp_output_path)
        if success:
            # Get the mime type
            print("mime_type", mime_type)

            if mime_type:
                if 'image' in mime_type:
                    # Handle GIF separately
                    if 'gif' in mime_type:
                        output_path = f"images/{uuid.uuid4()}.png"
                        if extract_first_frame_from_gif(temp_output_path, output_path):
                            return output_path
                    # Check if the image is webp or any other format we need to convert
                    elif 'webp' in mime_type:
                        output_path = f"images/{uuid.uuid4()}.png"
                        if convert_image_to_png(temp_output_path, output_path):
                            return output_path
                    else:
                        output_path = f"images/{uuid.uuid4()}.png"
                        if convert_image_to_png(temp_output_path, output_path):
                            return output_path
                elif 'video' in mime_type or 'gif' in mime_type:
                    output_path = f"images/{uuid.uuid4()}.png"
                    if extract_first_frame_from_video(url, output_path):
                        return output_path

    return None  # Return None if no media could be retrieved


if __name__ == '__main__':
    print(remove_emojis("⚡ Text"))
