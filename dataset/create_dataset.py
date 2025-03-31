import json
import os

from network_tools import NetworkToolsAPI, GptModels

from dataset_funcs import create_text_chunks_from_files, parse_to_json

# Папка с текстовыми файлами
# Использовались файлы с транскрипцией стримов
folder_path = r'E:\Games\datasets_other\row_text'
network_tools_api = "API_KEY"  # ключ NetworkToolsAPI
character_name = "CHARACTER NAME"  # Имя персонажа

# Выходные файлы
formatted_dataset = f"formatted-dataset-{character_name}.txt"
sorted_dataset = f"dataset-sorted-{character_name}.txt"
sorted_dataset_json = f"dataset_json/{character_name}.json"

# Можете настроить min_size и max_size вручную, но не рекомендую.
chunks = create_text_chunks_from_files(folder_path, min_size=5000, max_size=6000)

for chunk in chunks:
    print(f"Длина куска \"{chunk[:20]} ... {chunk[-20:]}\": {len(chunk)}")

print(f'Количество кусков текста: {len(chunks)}')

network_client = NetworkToolsAPI(api_key=network_tools_api)

if not os.path.exists(formatted_dataset):
    with open(formatted_dataset, "w", encoding="utf-8", errors="ignore"):
        pass

input("Press Enter to continue")
print("Part 1. Форматирование.")
# Part 1. Форматирование (формат вопрос-ответ)

for i, text_chunk in enumerate(chunks):
    prompt = ("# Задача\n\n"
              "Выведи информацию об этом человеке в формате вопрос-ответ.\n\n"
              "# Пример\n"
              "## Вопрос\n"
              "Как тебя зовут?\n"
              "## Ответ\n"
              "Меня зовут ...\n\n"
              "# Информация\n\n")
    answer = network_client.chatgpt_api(prompt=prompt + text_chunk, model=GptModels.chatgpt_4o)
    print(f"got answer {i + 1}: {answer.response.text[:20]} ...")
    with open(formatted_dataset, "a", encoding="utf-8", errors="ignore") as writer:
        writer.write(answer.response.text + "\n\n====\n\n")

input("Press Enter to continue")
print("Part 2. Сортировка по темам")
# Part 2. Сортировка по темам. Можете написать конкретные темы для повышения качества.
# Также рекомендую убрать лишние вопросы из "formatted-dataset-.txt"

with open(formatted_dataset, "r", encoding="utf-8", errors="ignore") as reader:
    content = reader.read()
    summarized_answers = content.split("===")

if not os.path.exists(sorted_dataset):
    with open(sorted_dataset, "w", encoding="utf-8", errors="ignore"):
        pass

for i in range(0, len(summarized_answers), 3):  # 3 за раз
    summarized_chunk = "\n\n".join(summarized_answers[i:i + 3])

    prompt = ("# Задача\n\n"
              "1. Нужно отсортировать вопросы и ответы по темам.\n"
              "2. Объедини похожие и одинаковы вопросы\n"
              "Темы: \n"
              "- Проекты и творчество\n"  # TODO можете написать конкретные темы для повышения качества.
              "- Увлечения\n"
              "- Характер персонажа\n"
              "- Прочее\n"
              "...\n\n"
              "# Формат ответа\n\n"
              "\"\"\"\n"
              "## Проекты и творчество\n"
              "### Вопрос\n"
              "...\n"
              "### Ответ\n"
              "...\n"
              "\"\"\"\n\n"
              "# Вопросы и ответы для сортировки\n\n")

    # Call the API with the concatenated chunk (or fewer elements if it's the last batch)
    answer = network_client.chatgpt_api(prompt=prompt + summarized_chunk, model=GptModels.chatgpt_4o)

    print(f"got answer {i // 3 + 1}: {answer.response.text[:20]} ...")

    # Write the response to the output file
    with open(sorted_dataset, "a", encoding="utf-8", errors="ignore") as writer:
        writer.write(answer.response.text + "\n\n====\n\n")

input("Press Enter to continue")
print("Part 3. Форматирование в JSON")

with open(sorted_dataset, 'r', encoding='utf-8') as file:
    text = file.read()
result = parse_to_json(text)
with open(sorted_dataset_json, 'w', encoding='utf-8') as file:
    json.dump(result, file, ensure_ascii=False, indent=4)

print(f"Датасет 'вопрос-ответ' сохранён: {formatted_dataset}")

# Автоматически при первом запуске:

# input("Press Enter to continue")
# print("Part 4. Создание embeddings. Нужен API-key Huggingface")
#
# hf_token = secret.hf_token  # (бесплатно) https://huggingface.co/settings/tokens
# tools = EmbeddingTools(hf_token, "dataset")
# tools.process_folder()
