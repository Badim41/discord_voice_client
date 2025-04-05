import hashlib
import json
import os
import re
import subprocess
import uuid

import magic
import requests
from PIL import Image
from discord_user.utils.re_str import extract_discord_emojis


def split_text_by_sentences(text, min_size=5000, max_size=6000):
    # Регулярное выражение для поиска предложений (основное для английского текста)
    sentence_endings = re.compile(r'([.!?])')

    # Разделение текста на предложения
    sentences = sentence_endings.split(text)
    sentences = [s.strip() for s in sentences if s.strip()]  # Убираем пустые строки

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        # Добавляем предложение к текущему куску текста
        if len(current_chunk) + len(sentence) + 1 > max_size:
            if len(current_chunk) >= min_size:
                chunks.append(current_chunk)
                current_chunk = sentence  # Начинаем новый кусок
            else:
                current_chunk += " " + sentence  # Слишком маленький кусок, добавляем ещё предложения
        else:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence

    if current_chunk:  # Добавляем последний кусок
        chunks.append(current_chunk)

    return chunks


def create_text_chunks_from_files(folder_path, min_size=5000, max_size=6000):
    all_chunks = []

    # Прочитать все файлы в указанной папке
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        # Пропускаем, если это не текстовый файл
        if not os.path.isfile(file_path) or not filename.endswith('.txt'):
            continue

        with open(file_path, 'r', encoding='utf-8') as file:
            text = file.read()
            chunks = split_text_by_sentences(text, min_size=min_size, max_size=max_size)
            all_chunks.extend(chunks)

    return all_chunks

def parse_to_json(text):
    # Разделяем текст на строки
    lines = text.strip().split('\n')

    # Инициализируем результат
    result = {}

    # Регулярные выражения для поиска заголовков и подзаголовков
    header_pattern = r'^##\s+(.+)$'
    question_pattern = r'^###\s+Вопрос\s*$'
    answer_pattern = r'^###\s+Ответ\s*$'

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Проверяем заголовок уровня ##
        header_match = re.match(header_pattern, line)
        if header_match:
            current_header = header_match.group(1)
            # Если заголовок еще не существует, создаем пустой список
            if current_header not in result:
                result[current_header] = []
            i += 1
            continue

        # Проверяем начало вопроса
        question_match = re.match(question_pattern, line)
        if question_match and current_header:
            i += 1
            # Собираем текст вопроса до следующего ###
            question_text = []
            while i < len(lines) and not re.match(r'^###\s+', lines[i]):
                if lines[i].strip():
                    question_text.append(lines[i].strip())
                i += 1
            question = ' '.join(question_text)

            # Ищем ответ
            if i < len(lines) and re.match(answer_pattern, lines[i]):
                i += 1
                answer_text = []
                while i < len(lines) and not re.match(r'^###\s+', lines[i]) and not re.match(header_pattern, lines[i]):
                    if lines[i].strip():
                        answer_text.append(lines[i].strip())
                    i += 1
                answer = ' '.join(answer_text)
                result[current_header].append({question: answer})
            continue

        i += 1

    return result

# def parse_file_content(content):
#     # Разделяем содержимое на строки
#     lines = content.strip().split('\n')
#
#     # Инициализируем список для пар вопрос-ответ
#     qa_pairs = []
#     current_question = None
#
#     # Регулярные выражения для поиска вопросов и ответов
#     question_pattern = r'^Вопрос:\s+(.+)$'
#     answer_pattern = r'^Ответ:\s+(.+)$'
#
#     i = 0
#     while i < len(lines):
#         line = lines[i].strip()
#
#         # Проверяем вопрос
#         question_match = re.match(question_pattern, line)
#         if question_match:
#             current_question = question_match.group(1)
#             i += 1
#             continue
#
#         # Проверяем ответ
#         answer_match = re.match(answer_pattern, line)
#         if answer_match and current_question:
#             answer = answer_match.group(1)
#             qa_pairs.append({current_question: answer})
#             current_question = None
#             i += 1
#             continue
#
#         i += 1
#
#     return qa_pairs
#
#
# def process_folder(folder_path):
#     # Инициализируем результат
#     result = {}
#
#     # Проходим по всем файлам в папке
#     for filename in os.listdir(folder_path):
#         if filename.endswith('.txt'):
#             # Получаем имя файла без расширения как заголовок
#             header = os.path.splitext(filename)[0]
#
#             # Читаем содержимое файла
#             file_path = os.path.join(folder_path, filename)
#             with open(file_path, 'r', encoding='utf-8') as file:
#                 content = file.read()
#
#             # Парсим содержимое файла
#             qa_pairs = parse_file_content(content)
#             result[header] = qa_pairs
#
#     return result
#
#
# if __name__ == '__main__':
#     # Пример использования
#     folder_path = r'folder'  # Укажите путь к папке
#     result = process_folder(folder_path)
#
#     # Преобразуем в JSON и сохраняем
#     json_output = json.dumps(result, ensure_ascii=False, indent=4)
#     print(json_output)
#
#     # Опционально: сохранение в файл
#     with open('output.json', 'w', encoding='utf-8') as f:
#         json.dump(result, f, ensure_ascii=False, indent=4)

def get_mime_type_from_content(file_path):
    try:
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(file_path)
        return mime_type
    except Exception as e:
        print(f"Error detecting MIME type with python-magic: {e}")
        return None

def download_content(url, output_file, attempts=10):
    for i in range(attempts):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()

            with open(output_file, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
            # Определяем MIME-тип по содержимому файла
            mime_type = get_mime_type_from_content(output_file)
            return True, mime_type or 'image/NotFound'
        except Exception as e:
            print(f"Temp error in download: {e}")
    return False, None

def convert_image_to_png(input_file, output_file):
    try:
        with Image.open(input_file) as img:
            img.convert("RGBA").save(output_file, "PNG")
        return True
    except Exception as e:
        print(f"Error converting image to PNG: {e}")
        return False


def extract_first_frame_from_gif(input_file, output_file):
    try:
        with Image.open(input_file) as img:
            # Extract the first frame from the GIF
            img.seek(0)
            img.save(output_file, "PNG")
        return True
    except Exception as e:
        print(f"Error extracting frame from GIF: {e}")
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
        print(f"Error extracting frame from video: {e}")
        return False

def download_image_path_from_message(file_name, message_json):  # Изменено с message на message_json
    os.makedirs('images', exist_ok=True)
    emojies_in_message = extract_discord_emojis(message_json['content'])  # Изменено message.text на message_json['content']

    attachment_urls = []

    if message_json.get('attachments'):  # Изменено message.attachments на message_json['attachments']
        attachment_urls = [attachment['url'] for attachment in message_json['attachments']]

    print("attachment_urls", attachment_urls)
    for url in attachment_urls:
        # Download the content
        temp_output_path = f"images/{file_name}.tmp"
        success, mime_type = download_content(url, temp_output_path)
        if success:
            # Get the mime type
            print("mime_type", mime_type)

            if mime_type:
                if 'image' in mime_type:
                    if 'webp' in mime_type:
                        output_path = f"images/{file_name}.png"
                        if convert_image_to_png(temp_output_path, output_path):
                            return output_path
                    else:
                        output_path = f"images/{file_name}.png"
                        if convert_image_to_png(temp_output_path, output_path):
                            return output_path

    return None  # Return None if no media could be retrieved


def get_hash(input_string: str, algorithm: str = 'sha256') -> str:
    """
    Получает хэш строки с использованием заданного алгоритма.

    :param input_string: Строка для хэширования.
    :param algorithm: Алгоритм хэширования ('sha256', 'md5', 'sha1' и т.д.).
    :return: Хэш строки в виде шестнадцатеричной строки.
    """
    try:
        hash_function = getattr(hashlib, algorithm)
    except AttributeError:
        raise ValueError(
            f"Алгоритм '{algorithm}' не поддерживается. Используйте один из {', '.join(hashlib.algorithms_guaranteed)}.")

    hash_object = hash_function(input_string.encode('utf-8'))
    return hash_object.hexdigest()
