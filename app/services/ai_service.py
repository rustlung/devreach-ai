from __future__ import annotations

import logging
import time
from typing import Protocol

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
from pydantic import ValidationError

from app.ai.prompts import AI_ANALYSIS_SYSTEM_PROMPT
from app.core.config import Settings, get_settings
from app.schemas.ai import AIAnalysisResult, AIServiceResult
from app.schemas.contact_storage import AiStatus, ContactCategory, ContactPriority, Sentiment

logger = logging.getLogger(__name__)


class AIAnalysisService(Protocol):
    def analyze_comment(self, comment: str) -> AIServiceResult:
        ...


def build_fallback_analysis() -> AIAnalysisResult:
    return AIAnalysisResult(
        sentiment=Sentiment.NEUTRAL,
        category=ContactCategory.OTHER,
        priority=ContactPriority.NORMAL,
        summary=None,
        suggested_reply="Спасибо за обращение. Сообщение получено, я свяжусь с вами после ознакомления.",
    )


def build_fallback_result(error_code: str, error_message: str | None = None) -> AIServiceResult:
    # Fallback — нормальный устойчивый результат pipeline: обращение можно сохранить
    # и обработать дальше, не раскрывая пользователю техническую причину сбоя AI.
    return AIServiceResult(
        analysis=build_fallback_analysis(),
        status=AiStatus.FALLBACK,
        error_code=error_code,
        error_message=error_message,
    )


class OpenAIAnalysisService:
    def __init__(self, settings: Settings | None = None, client: OpenAI | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def analyze_comment(self, comment: str) -> AIServiceResult:
        start_time = time.perf_counter()
        logger.info(
            "event=ai_analysis_started provider=openai model=%s comment_length=%s",
            self.settings.openai_model,
            len(comment),
        )

        if not self.settings.ai_live_requests_enabled:
            return self._fallback("live_requests_disabled", "Live-вызовы OpenAI отключены настройкой")

        if not self.settings.openai_api_key:
            return self._fallback("missing_api_key", "OPENAI_API_KEY не задан")

        try:
            response = self._get_client().chat.completions.parse(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": AI_ANALYSIS_SYSTEM_PROMPT},
                    # Комментарий передаётся отдельно от system prompt: это снижает риск
                    # prompt injection и не превращает пользовательский текст в инструкции.
                    {"role": "user", "content": comment},
                ],
                response_format=AIAnalysisResult,
            )
            parsed_result = response.choices[0].message.parsed
            if parsed_result is None:
                return self._fallback("empty_response", "OpenAI вернул пустой structured output")

            # Structured output всё равно валидируем Pydantic-моделью явно:
            # так будущие изменения SDK или тестовые заглушки не обходят контракт сервиса.
            analysis = AIAnalysisResult.model_validate(parsed_result)
        except APITimeoutError as exc:
            return self._fallback("api_timeout", "OpenAI API timeout", exc)
        except APIConnectionError as exc:
            return self._fallback("api_connection_error", "Ошибка соединения с OpenAI", exc)
        except AuthenticationError as exc:
            return self._fallback("api_auth_error", "Ошибка авторизации OpenAI", exc)
        except RateLimitError as exc:
            return self._fallback("api_rate_limit", "OpenAI rate limit", exc)
        except APIError as exc:
            return self._fallback("api_error", "Ошибка OpenAI API", exc)
        except ValidationError as exc:
            logger.warning(
                "event=ai_response_validation_failed error_type=%s fallback_applied=true",
                type(exc).__name__,
            )
            return self._fallback("invalid_structured_output", "OpenAI вернул некорректный structured output", exc)
        except (IndexError, AttributeError) as exc:
            return self._fallback("empty_response", "OpenAI вернул ответ без результата", exc)
        except Exception as exc:
            logger.exception(
                "event=ai_unexpected_error error_type=%s fallback_applied=true",
                type(exc).__name__,
            )
            return self._fallback("unexpected_error", "Неожиданная ошибка AI-сервиса", exc)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "event=ai_analysis_completed provider=openai model=%s sentiment=%s category=%s priority=%s duration_ms=%s",
            self.settings.openai_model,
            analysis.sentiment.value,
            analysis.category.value,
            analysis.priority.value,
            duration_ms,
        )
        return AIServiceResult(analysis=analysis, status=AiStatus.SUCCESS)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            # Клиент создаётся лениво: импорт приложения и обычные тесты не должны
            # требовать API-ключ и не должны случайно готовить live-запрос.
            self._client = OpenAI(
                api_key=self.settings.openai_api_key,
                timeout=self.settings.openai_timeout_seconds,
                max_retries=self.settings.openai_max_retries,
            )
        return self._client

    def _fallback(
        self,
        error_code: str,
        error_message: str,
        exc: Exception | None = None,
    ) -> AIServiceResult:
        logger.warning(
            "event=ai_fallback_applied reason=%s error_type=%s fallback_applied=true",
            error_code,
            type(exc).__name__ if exc else None,
        )
        return build_fallback_result(error_code=error_code, error_message=error_message)


class FakeAIAnalysisService:
    def __init__(
        self,
        mode: str = "success",
        analysis: AIAnalysisResult | None = None,
    ) -> None:
        self.mode = mode
        self.analysis = analysis or AIAnalysisResult(
            sentiment=Sentiment.NEUTRAL,
            category=ContactCategory.PROJECT_REQUEST,
            priority=ContactPriority.NORMAL,
            summary="Тестовое обращение о проекте.",
            suggested_reply="Спасибо за обращение. Я ознакомлюсь с деталями и свяжусь с вами.",
        )

    def analyze_comment(self, comment: str) -> AIServiceResult:
        if self.mode == "error":
            raise RuntimeError("Тестовая ошибка fake AI")
        if self.mode == "fallback":
            return build_fallback_result("fake_fallback", "Fake fallback")
        return AIServiceResult(analysis=self.analysis, status=AiStatus.SUCCESS)
