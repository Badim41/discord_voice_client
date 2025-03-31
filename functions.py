def format_messages(messages, max_length: int = None):
    formatted_messages = []
    current_length = 0

    # Обрабатываем сообщения в обратном порядке для приоритета новым,
    # но потом развернем для сохранения исходного порядка
    for message in reversed(messages):
        role = message.get('role', '').upper()
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
        formatted_message = f"## {role}:\n{content_str.strip()}\n"

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
