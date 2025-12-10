import requests
import logging


GEMINI_API_KEY = "AIzaSyBfxC1LZ8x17UcHUi0oLQC72mcUPaeGg-w" 
MODEL_NAME = 'gemini-2.0-flash' 
# FILE_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/files"

# Настройка логгера
logger = logging.getLogger("ai") # Используем тот же логгер, что и в main.py
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(asctime)s][%(levelname)s][AI][GeminiAPI] %(message)s'))
    logger.addHandler(handler)

class GeminiAPI:
    """
    Класс для взаимодействия с Gemini API.
    """
    def __init__(self, api_key=GEMINI_API_KEY, model=MODEL_NAME, max_tokens=100000):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        # Формируем базовый URL для API
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        logger.info(f"Инициализация GeminiAPI с моделью: {self.model}, лимит токенов: {self.max_tokens}")

    def generate_content(self, prompt):
        """Отправляет запрос на генерацию контента в Gemini API.

        Args:
            prompt (str): Входной текст для генерации.

        Returns:
            dict: JSON-ответ от Gemini API.

        Raises:
            requests.exceptions.RequestException: Если произошла ошибка HTTP-запроса.
            ValueError: Если ответ от API не содержит ожидаемых данных.
        """
        headers = {
            "Content-Type": "application/json",
        }
        params = {
            "key": self.api_key # Ключ API передается как параметр запроса
        }
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": self.max_tokens
            }
        }
        logger.info(f"Отправка запроса в Gemini. Длина промпта: {len(prompt)} символов")

        try:
            response = requests.post(self.base_url, headers=headers, params=params, json=data, verify=False)
            response.raise_for_status() # Вызывает HTTPError для плохих ответов (4xx или 5xx)
            
            logger.info(f"Ответ от Gemini: status_code={response.status_code}")
            
            json_response = response.json()
            
            # Проверка структуры ответа
            if json_response and 'candidates' in json_response and \
               len(json_response['candidates']) > 0 and \
               'content' in json_response['candidates'][0] and \
               'parts' in json_response['candidates'][0]['content'] and \
               len(json_response['candidates'][0]['content']['parts']) > 0 and \
               'text' in json_response['candidates'][0]['content']['parts'][0]:
                logger.info(f"Успешный ответ от Gemini. Длина ответа: {len(response.text)} символов")
                return json_response
            else:
                logger.error(f"Неожиданная структура ответа от Gemini: {json_response}")
                raise ValueError("Неожиданная структура ответа от Gemini")

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP ошибка при запросе к Gemini: {e.response.status_code} - {e.response.text}")
            raise requests.exceptions.RequestException(f"Ошибка HTTP: {e.response.status_code} - {e.response.text}")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ошибка подключения при запросе к Gemini: {e}")
            raise requests.exceptions.RequestException(f"Ошибка подключения к Gemini: {e}")
        except requests.exceptions.Timeout as e:
            logger.error(f"Таймаут при запросе к Gemini: {e}")
            raise requests.exceptions.RequestException(f"Таймаут запроса к Gemini: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Общая ошибка запроса к Gemini: {e}")
            raise
        except ValueError as e:
            logger.error(f"Ошибка обработки JSON или структуры ответа: {e}")
            raise
        except Exception as e:
            logger.error(f"Непредвиденная ошибка в GeminiAPI: {e}")
            raise

    def upload_file(self, file_data, file_name, mime_type):
        url = f"{FILE_API_BASE_URL}?key={self.api_key}"

        metadata = {
            "display_name": file_name,
            "mime_type": mime_type
        }

        data = {
            "metadata": json.dumps(metadata)
        }

        files = {
            "file": (file_name, file_data, mime_type)
        }

        self.logger.info(f"Загрузка файла: {file_name}")

        try:
            response = requests.post(url, data=data, files=files)

            if not response.ok:
                self.logger.error(
                    f"File API Error {response.status_code}: {response.text}"
                )
                response.raise_for_status()

            json_response = response.json()

            if "name" in json_response:
                self.logger.info(f"Файл загружен: {json_response['name']}")
                return json_response

            raise ValueError(f"Неожиданный ответ: {json_response}")

        except Exception as e:
            self.logger.error(f"Ошибка загрузки файла: {e}")
            raise
            
    def generate_content_with_file(self, file_name: str, prompt: str):
        """Отправляет запрос на генерацию контента, используя ранее загруженный файл."""
        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}
        
        # Формируем `contents` для передачи файла
        data = {
            "contents": [{
                "parts": [
                    {"fileData": {"mimeType": "application/pdf", "fileUri": file_name}}, # MimeType лучше брать из загрузки
                    {"text": prompt}
                ]
            }],
            "generationConfig": {"maxOutputTokens": self.max_tokens}
        }
        
        # ... (Остальная часть generate_content, начиная с try: response = requests.post...)
        # Вы можете переиспользовать существующую логику generate_content, просто изменив data.
