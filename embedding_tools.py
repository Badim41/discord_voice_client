import json
import os
import time
from functools import lru_cache
from typing import List, Union

import numpy as np
import requests
from network_tools import NetworkToolsAPI
from requests import RequestException
from requests.adapters import HTTPAdapter
from scipy.spatial.distance import cosine
from urllib3.util.retry import Retry

import secret
from base_logger import Logs
from functions import convert_answer_to_json

logger = Logs(warnings=True, name="embedding-tools")

search_dataset_prompt = secret.search_dataset_prompt
search_dataset_model = secret.search_dataset_model


class EmbeddingTools:
    def __init__(self, cohere_api_keys: list, dataset_folder, proxies=None, network_client: NetworkToolsAPI = None):
        """Инициализация с токеном HF и папкой для поиска"""
        self.cohere_api_keys = cohere_api_keys
        self._all_cohere_api_keys: list = cohere_api_keys
        self.network_client = network_client
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
            self,
            text: Union[str, List[str]],
            model: str = "embed-english-v3.0",
            input_type: str = "classification",
            embedding_type: str = "float",
            max_retries: int = 45,
            base_delay: float = 1.0
    ) -> List[float]:
        """
        Генерация эмбеддинга через Cohere API v2/embed с улучшенной обработкой лимитов и ошибок.

        Args:
            text: Текст или список текстов для получения эмбеддингов
            model: Название модели
            input_type: Тип ввода (search_document, search_query, classification, clustering, image)
            embedding_type: Тип возвращаемых эмбеддингов (float, int8, uint8, binary, ubinary)
            max_retries: Максимальное количество попыток
            base_delay: Базовая задержка между повторными попытками в секундах

        Returns:
            Список чисел с плавающей точкой представляющих эмбеддинг

        Raises:
            ValueError: Некорректные входные параметры
            RequestException: Ошибка при запросе к API после всех попыток
            Exception: Отсутствуют API ключи
        """

        def _handle_rate_limit(response_text: str, attempt: int, base_delay: float, api_key: str,
                               current_keys: list) -> float:
            """Обработка различных типов ограничений скорости."""
            if "calls / minute" in response_text:
                return 20.0
            elif "Please wait and try again later" in response_text:
                return 10.0
            elif "1000 API calls / month" in response_text:
                # Удаляем ключ навсегда
                if api_key in self._all_cohere_api_keys:
                    logger.logging(f"removed: {api_key}")
                    self._all_cohere_api_keys.remove(api_key)
                if api_key in current_keys:
                    current_keys.remove(api_key)
                return None  # Сигнализируем, что ключ удалён и нужно продолжить с новым
            return base_delay * (attempt + 1)

        # Валидация входных параметров
        if not text:
            raise ValueError("Text parameter cannot be empty")
        if not self.cohere_api_keys and not self._all_cohere_api_keys:
            raise Exception("No Cohere API keys available")

        # Подготовка запроса
        payload = {
            "model": model,
            "texts": [text] if isinstance(text, str) else text,
            "input_type": input_type,
            "embedding_types": [embedding_type]
        }

        headers_template = {
            "accept": "application/json",
            "content-type": "application/json"
        }

        start_time = time.time()
        current_keys = self.cohere_api_keys or self._all_cohere_api_keys

        for attempt in range(max_retries):
            if not current_keys:
                print(f"No keys. Update: {self._all_cohere_api_keys}")
                current_keys = self._all_cohere_api_keys
                if not current_keys:
                    raise Exception("All Cohere API keys exhausted")

            api_key = current_keys[0]
            print(f"use: {api_key}")
            headers = {**headers_template, "Authorization": f"bearer {api_key}"}

            try:
                response = self.req_session.post(
                    "https://api.cohere.com/v2/embed",
                    json=payload,
                    headers=headers
                )
                status_code = response.status_code
                if status_code == 429:  # Rate limit
                    delay = _handle_rate_limit(response.text, attempt, base_delay, api_key, current_keys)
                    if delay is None:  # Ключ был удалён из-за лимита 1000 вызовов в месяц
                        continue
                    print(f"Слишком много запросов. Ждём {delay} с")
                    time.sleep(delay)
                    continue
                elif status_code == 401:  # Unauthorized
                    if api_key in self._all_cohere_api_keys:
                        logger.logging(f"removed: {api_key}")
                        self._all_cohere_api_keys.remove(api_key)
                    current_keys.pop(0)
                    continue
                response.raise_for_status()
                result = response.json()
                embeddings = result["embeddings"][embedding_type][0]

                logger.logging(f"Получен эмбеддинг: {time.time() - start_time:.2f}s")
                return embeddings

            except Exception as e:
                logger.logging(f"Request failed: {str(e)}")
                if attempt == max_retries - 1:
                    raise

            current_keys = current_keys[1:] or self._all_cohere_api_keys

        raise RequestException(f"Failed to get embedding after {max_retries} attempts")

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

    def remove_question_from_header(self, json_filename: str, question_text: str):
        """Удаляет вопрос по тексту из всех тем указанного JSON (и в dataset_json, и в dataset_embeddings)"""
        json_path = os.path.join(self.dataset_json_folder, json_filename)
        embed_path = os.path.join(self.dataset_embeddings_folder, json_filename)

        # === Удаление из dataset_json ===
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            modified = False
            for header, qa_list in json_data.items():
                new_qa_list = [qa for qa in qa_list if question_text not in qa]
                if len(new_qa_list) != len(qa_list):
                    json_data[header] = new_qa_list
                    modified = True

            if modified:
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)

        else:
            logger.logging(f"Файл не найден: {json_path}")

        # === Удаление из dataset_embeddings ===
        if os.path.exists(embed_path):
            with open(embed_path, 'r', encoding='utf-8') as f:
                embed_data = json.load(f)

            modified = False
            for header, items in embed_data.items():
                new_items = [items[0]]  # Сохраняем первый элемент — эмбеддинг заголовка
                changed = False
                for item in items[1:]:
                    if item.get("question") != question_text:
                        new_items.append(item)
                    else:
                        changed = True
                if changed:
                    embed_data[header] = new_items
                    modified = True

            if modified:
                with open(embed_path, 'w', encoding='utf-8') as f:
                    json.dump(embed_data, f, ensure_ascii=False, indent=2)

        else:
            logger.logging(f"Файл не найден: {embed_path}")
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

    def search_similar_questions(self, query, embeddings_dataset, top_k=3):
        """Поиск наиболее похожих вопросов в данных нескольких JSON"""
        query_embedding = np.array(self.get_embedding(query, max_retries=20))

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
                        "similarity": similarity + (header_similarity / 2),
                        "header_similarity": header_similarity,
                        "question_similarity": question_similarity,
                        "answer_similarity": answer_similarity
                    })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def get_memories(
            self,
            query,
            specific_files=None,
            min_results=1,
            max_results=5,
            deepsearch=False,
            file_path=None,
            formatted_chat_history=""
    ):
        search_prompts = []
        if deepsearch:
            if not self.network_client:
                logger.logging("Не указан network_client. Нельзя делать DeepSearch")
                return ""
            if formatted_chat_history:
                formatted_chat_history = f"# История сообщения\n{formatted_chat_history}\n\n"
            answer_gpt = self.network_client.chatgpt_api(
                f"{search_dataset_prompt}\n\n{formatted_chat_history}\n\n# Текущий запрос\n{query}",
                model=search_dataset_model,
                file_path=file_path
            )
            converted, json_answer = convert_answer_to_json(
                answer_gpt.response.text,
                end_symbol="]",
                start_symbol="[",
                keys=[]
            )
            if not converted:
                logger.logging(f"Не конвертировался ответ: {json_answer}")
                search_prompts.append(query)
            else:
                search_prompts = json_answer
        else:
            search_prompts.append(query)

        all_similar_items = []
        questions_was = []

        for search_prompt in search_prompts:
            try:
                embeddings_dataset = self.get_embeddings_dataset(specific_files)
                similar_items = self.search_similar_questions(search_prompt, embeddings_dataset, top_k=100)

                for item in similar_items:
                    if item['question'] not in questions_was:
                        all_similar_items.append(item)
                        questions_was.append(item['question'])

            except Exception as e:
                logger.logging(f"ERROR: Не удалось выполнить get_memories: {e}")

        # Сортировка по убыванию схожести и обрезка до max_results
        all_similar_items = sorted(all_similar_items, key=lambda x: x['similarity'], reverse=True)[:max_results]

        # Сортировка обратно по возрастанию для вывода
        all_similar_items = sorted(all_similar_items, key=lambda x: x['similarity'])

        all_similar_items = [item for item in all_similar_items if item['similarity'] > 0.80]

        if not all_similar_items:
            return ""

        output_result = "# Память персонажа\n"
        last_info = ""
        for item in all_similar_items:
            result_this = ""
            info_str = f"### Информация о '{item['json_name'][:-5]}'\n"
            if info_str != last_info:
                result_this += info_str
                last_info = info_str

            result_this += f"#### Тема: {item['header']}\n"
            result_this += f"Вопрос: {item['question']}\n"
            result_this += f"Ответ: {item['answer']}\n"
            result_this += f"Схожесть вопроса с текущим: {item['similarity']:.2f}\n"
            output_result += result_this

        return output_result


# Пример использования
if __name__ == "__main__":
    # Инициализация
    cohere_api_keys = secret.cohere_api_keys
    dataset_folder = "dataset"  # Укажите путь к корневой папке
    tools = EmbeddingTools(cohere_api_keys, dataset_folder)

    # Обработка папки dataset_json и сохранение в dataset_embeddings
    tools.process_folder()
    print("Processing complete")

    prompt = "Кто такой ...?"
    result = tools.get_memories(prompt)
    print(result)

    tools.remove_question_from_header("FILE.json", question_text="TEXT")

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
