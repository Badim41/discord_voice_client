import json
import os
import time
from functools import lru_cache
from typing import List, Union

import numpy as np
import requests
from requests import RequestException
from requests.adapters import HTTPAdapter
from scipy.spatial.distance import cosine
from urllib3.util.retry import Retry

import secret
from base_logger import Logs
from functions import Time_Count

logger = Logs(warnings=True, name="embedding-tools")


class EmbeddingTools:
    def __init__(self, cohere_api_key, dataset_folder, proxies=None):
        """Инициализация с токеном HF и папкой для поиска"""
        self.cohere_api_key = cohere_api_key
        self.dataset_folder = dataset_folder
        self.dataset_json_folder = os.path.join(self.dataset_folder, "dataset_json")
        self.dataset_embeddings_folder = os.path.join(self.dataset_folder, "dataset_embeddings")

        self.req_session = requests.Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
        self.req_session.mount('http://', HTTPAdapter(max_retries=retries))
        self.req_session.mount('https://', HTTPAdapter(max_retries=retries))
        if proxies:
            self.req_session.proxies = proxies

    @lru_cache(maxsize=10 ** 5)
    def get_embedding(
            self, text: Union[str, List[str]],
            model: str = "embed-english-v3.0",
            input_type: str = "classification",
            embedding_type: str = "float",
            max_retries=6,
            timeout=60
    ) -> List[float]:
        """
        Генерация эмбеддинга через Cohere API v2/embed с обработкой лимитов

        Args:
            text: Текст или список текстов для получения эмбеддингов
            model: Название модели (по умолчанию embed-english-v3.0)
            input_type: Тип ввода (search_document, search_query, classification, clustering, image)
            embedding_type: Тип возвращаемых эмбеддингов (float, int8, uint8, binary, ubinary)

        Returns:
            Список чисел с плавающей точкой представляющих эмбеддинг

        Raises:
            requests.exceptions.RequestException: Ошибка при запросе к API после всех попыток
        """
        timer = Time_Count()  # Предполагается, что у вас есть такой класс

        # Формируем тело запроса
        payload = {
            "model": model,
            "texts": [text] if isinstance(text, str) else text,
            "input_type": input_type,
            "embedding_types": [embedding_type]
        }

        # Настраиваем заголовки
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"bearer {self.cohere_api_key}"
        }

        base_delay = 2  # базовая задержка в секундах

        for attempt in range(max_retries):
            try:
                # Отправляем запрос
                response = self.req_session.post(
                    "https://api.cohere.com/v2/embed",
                    json=payload,
                    headers=headers,
                    timeout=timeout
                )
                response.raise_for_status()

                # Получаем результат
                result = response.json()
                embeddings = result["embeddings"][embedding_type][0]

                logger.logging(f"Получен embedding: {timer.count_time()}")
                return embeddings

            except RequestException as e:
                if isinstance(e, requests.exceptions.Timeout):
                    logger.logging(f"Таймаут при запросе после {attempt + 1} попытки, завершаем")
                    break
                if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 429:
                    if attempt == max_retries - 1:  # Последняя попытка
                        logger.logging(f"Исчерпаны все попытки ({max_retries}) для получения эмбеддинга: {str(e)}")
                        break
                    # Экспоненциальная задержка: base_delay * (2 ^ attempt)
                    wait_time = base_delay * (2 ** attempt)
                    logger.logging(f"Получен 429, попытка {attempt + 1}/{max_retries}, ждем {wait_time} сек")
                    time.sleep(wait_time)
                else:
                    logger.logging(f"Ошибка при получении эмбеддинга: {str(e)}")
                    break

        # Этот код не должен быть достигнут из-за raise в последней попытке,
        # но добавлен для полноты
        raise RequestException("Не удалось получить эмбеддинг после всех попыток")

    def process_json_file(self, file_path):
        """Обрабатывает один JSON-файл и добавляет недостающие эмбеддинги"""
        with open(file_path, 'r', encoding='utf-8') as f:
            input_data = json.load(f)

        filename = os.path.basename(file_path)
        embeddings_file_path = os.path.join(self.dataset_embeddings_folder, filename)

        if os.path.exists(embeddings_file_path):
            with open(embeddings_file_path, 'r', encoding='utf-8') as f:
                embeddings_data = json.load(f)
        else:
            embeddings_data = {}

        result = {}

        for header, items in input_data.items():
            if (header in embeddings_data and
                    isinstance(embeddings_data[header], list) and
                    len(embeddings_data[header]) > 0 and
                    "embedings" in embeddings_data[header][0]):
                existing_items = embeddings_data[header]
                header_embedding = existing_items[0]["embedings"]
            else:
                header_embedding = self.get_embedding(header)
                existing_items = [{"embedings": header_embedding}]

            qa_pairs = []
            # Создаем словарь существующих вопросов для быстрого поиска
            existing_qa_dict = {item["question"]: item for item in existing_items[1:] if "question" in item}

            for qa in items:
                question = list(qa.keys())[0]
                answer = qa[question]

                if (question in existing_qa_dict and
                        "embeddings_question" in existing_qa_dict[question] and
                        "embeddings_answer" in existing_qa_dict[question]):
                    qa_pairs.append(existing_qa_dict[question])
                else:
                    question_embedding = self.get_embedding(question)
                    answer_embedding = self.get_embedding(answer)
                    qa_pairs.append({
                        "question": question,
                        "answer": answer,
                        "embeddings_question": question_embedding,
                        "embeddings_answer": answer_embedding
                    })

            result[header] = [
                {"embedings": header_embedding},  # Оставляем "embedings" для заголовка
                *qa_pairs
            ]

        return result

    def process_folder(self):
        """Обрабатывает JSON-файлы из dataset_json и сохраняет в dataset_embeddings"""
        os.makedirs(self.dataset_embeddings_folder, exist_ok=True)

        for filename in os.listdir(self.dataset_json_folder):
            if filename.endswith('.json'):
                input_file_path = os.path.join(self.dataset_json_folder, filename)
                output_file_path = os.path.join(self.dataset_embeddings_folder, filename)

                processed_data = self.process_json_file(input_file_path)

                with open(output_file_path, 'w', encoding='utf-8') as f:
                    json.dump(processed_data, f, ensure_ascii=False, indent=2)

    def add_qa_to_header(self, header, question, answer, output_file):
        """Добавляет вопрос и ответ в указанный заголовок в выходном JSON"""
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}

        question_embedding = self.get_embedding(question)
        answer_embedding = self.get_embedding(answer)

        if header in data:
            data[header].append({
                "question": question,
                "answer": answer,
                "embeddings_question": question_embedding,
                "embeddings_answer": answer_embedding
            })
        else:
            header_embedding = self.get_embedding(header)
            data[header] = [
                {"embedings": header_embedding},
                {
                    "question": question,
                    "answer": answer,
                    "embeddings_question": question_embedding,
                    "embeddings_answer": answer_embedding
                }
            ]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_embeddings_dataset(self, json_files=None):
        """Загружает данные из нескольких JSON. Если json_files - None, то все файлы JSON"""
        embeddings_dataset = {}

        if json_files is None:
            folder = self.dataset_embeddings_folder
            json_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.json')]

        for file_path in json_files:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                filename = os.path.basename(file_path)
                embeddings_dataset[filename] = data
            else:
                logger.logging(f"Warning: File {file_path} does not exist")

        return embeddings_dataset

    def search_similar_questions(self, query, embeddings_dataset, top_k=3, timeout=60):
        """Поиск наиболее похожих вопросов в данных нескольких JSON"""
        query_embedding = np.array(self.get_embedding(query, timeout=timeout))

        results = []

        for json_name, json_data in embeddings_dataset.items():
            for header, items in json_data.items():
                header_embedding = np.array(items[0]["embedings"])
                header_similarity = 1 - cosine(query_embedding, header_embedding)

                for qa in items[1:]:
                    question_embedding = np.array(qa["embeddings_question"])
                    answer_embedding = np.array(qa["embeddings_answer"])

                    # Считаем схожесть с вопросом и ответом
                    question_similarity = 1 - cosine(query_embedding, question_embedding)
                    answer_similarity = 1 - cosine(query_embedding, answer_embedding)

                    # Используем максимальную схожесть (вопрос или ответ)
                    similarity = max(question_similarity, answer_similarity)

                    results.append({
                        "json_name": json_name,
                        "header": header,
                        "question": qa["question"],
                        "answer": qa["answer"],
                        "similarity": similarity,
                        "header_similarity": header_similarity,
                        "question_similarity": question_similarity,
                        "answer_similarity": answer_similarity
                    })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def get_memories(self, query, specific_files=None, min_results=1, max_results=10, timeout=5):
        try:
            embeddings_dataset = self.get_embeddings_dataset(specific_files)
            output_result = "# Память персонажа\n"
            found_results = 0
            similar_items = self.search_similar_questions(query, embeddings_dataset, top_k=max_results, timeout=timeout)
            for i, item in enumerate(similar_items, 1):
                if item['similarity'] > 0.75 or found_results < min_results:
                    found_results += 1
                    output_result += f"## Результат {i}\n"
                    output_result += f"### Информация о '{item['json_name'][:-5]}'\n"
                    output_result += f"#### Тема: {item['header']}\n"
                    output_result += f"Вопрос: {item['question']}\n"
                    output_result += f"Ответ: {item['answer']}\n"
                    output_result += f"Схожесть вопроса с текущим: {item['similarity']:.3f}\n"
            return output_result
        except Exception as e:
            logger.logging(f"ERROR: Не удалось выполнить get_memories: {e}")
            return ""


# Пример использования
if __name__ == "__main__":
    # Инициализация
    cohere_api_key = secret.cohere_api_key  # (бесплатно) https://huggingface.co/settings/tokens
    dataset_folder = "dataset"  # Укажите путь к корневой папке
    tools = EmbeddingTools(cohere_api_key, dataset_folder)

    # Обработка папки dataset_json и сохранение в dataset_embeddings
    tools.process_folder()
    print("Processing complete")

    prompt = "Какую игру ты делаешь?"
    result = tools.get_memories(prompt)
    print(result)

    # # Добавление нового вопроса и ответа в конкретный файл
    # output_file = os.path.join(tools.dataset_embeddings_folder, "file1.json")
    # tools.add_qa_to_header("file1", "Новый вопрос", "Новый ответ", output_file)

    # # Пример загрузки данных из конкретных файлов
    # specific_files = [
    #     os.path.join(tools.dataset_embeddings_folder, "file1.json"),
    #     os.path.join(tools.dataset_embeddings_folder, "file2.json")
    # ]
    # specific_dataset = tools.get_embeddings_dataset(specific_files)
    # similar_items_specific = tools.search_similar_questions(query, specific_dataset, top_k=3)
    # print("\nSearch in specific files:")
    # for item in similar_items_specific:
    #     print(f"Header: {item['header']}")
    #     print(f"Question: {item['question']}")
    #     print(f"Answer: {item['answer']}")
    #     print(f"Similarity: {item['similarity']:.4f}")
    #     print(f"Header Similarity: {item['header_similarity']:.4f}")
    #     print("-" * 50)
