# app/modules/rag/gemini.py
"""
Обёртка для работы с Gemini API.
Поддерживает генерацию текста и embeddings.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import google.generativeai as genai

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Конфигурируем API key
genai.configure(api_key=settings.GEMINI_API_KEY)


class GeminiAPI:
    """
    Production-ready клиент для работы с Gemini API.

    Поддерживает:
    - Генерацию текста (LLM)
    - Embeddings для документов и запросов
    - Безопасную обработку ошибок
    - Логирование всех операций
    """

    def __init__(
        self,
        llm_model: str | None = None,
        embedding_model: str | None = None,
    ):
        self.llm_model = llm_model or settings.LIGHTRAG_LLM_MODEL
        self.embedding_model = embedding_model or settings.LIGHTRAG_EMBEDDING_MODEL

        logger.info(
            "GeminiAPI initialized",
            extra={
                "llm_model": self.llm_model,
                "embedding_model": self.embedding_model,
            },
        )

    def generate_content(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> str:
        """
        Генерирует текст через Gemini.

        Args:
            prompt: Входной промпт
            system_instruction: Системная инструкция (роль)
            temperature: Температура генерации (0.0-1.0)
            max_tokens: Максимальное количество токенов

        Returns:
            Сгенерированный текст
        """
        try:
            model = genai.GenerativeModel(
                model_name=self.llm_model,
                system_instruction=system_instruction,
            )

            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )

            logger.info(
                "Gemini content generated",
                extra={
                    "prompt_length": len(prompt),
                    "response_length": len(response.text) if response.text else 0,
                },
            )

            return response.text

        except Exception as e:
            logger.error(
                "Gemini generation error",
                extra={"error": str(e), "prompt_length": len(prompt)},
            )
            raise

    def embed_text(
        self,
        text: str | List[str],
        task_type: str = "retrieval_document",
    ) -> List[float] | List[List[float]]:
        """
        Генерирует embeddings через Gemini Embedding API.

        Args:
            text: Текст или список текстов для эмбеддинга
            task_type: Тип задачи ('retrieval_document' или 'retrieval_query')

        Returns:
            Вектор или список векторов
        """
        try:
            if isinstance(text, str):
                result = genai.embed_content(
                    model=self.embedding_model,
                    content=text,
                    task_type=task_type,
                )

                logger.info(
                    "Gemini embedding generated",
                    extra={
                        "text_length": len(text),
                        "task_type": task_type,
                    },
                )

                return result["embedding"]
            else:
                # Batch embeddings
                embeddings = []
                for txt in text:
                    result = genai.embed_content(
                        model=self.embedding_model,
                        content=txt,
                        task_type=task_type,
                    )
                    embeddings.append(result["embedding"])

                logger.info(
                    "Gemini batch embeddings generated",
                    extra={
                        "batch_size": len(text),
                        "task_type": task_type,
                    },
                )

                return embeddings

        except Exception as e:
            logger.error(
                "Gemini embedding error",
                extra={"error": str(e)},
            )
            raise

    def embed_query(self, query: str) -> List[float]:
        """
        Генерирует embedding для поискового запроса.

        Args:
            query: Поисковый запрос

        Returns:
            Вектор запроса
        """
        return self.embed_text(query, task_type="retrieval_query")

    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """
        Генерирует embeddings для документов.

        Args:
            documents: Список текстов документов

        Returns:
            Список векторов
        """
        return self.embed_text(documents, task_type="retrieval_document")
