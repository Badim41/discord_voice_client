import json
import os
import re
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
