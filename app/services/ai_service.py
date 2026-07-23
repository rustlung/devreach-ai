from __future__ import annotations

import logging
import re
import time
from typing import Protocol

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import ValidationError

from app.ai.prompts import AI_ANALYSIS_SYSTEM_PROMPT
from app.core.config import Settings, get_settings
from app.schemas.ai import AIAnalysisResult, AIServiceResult
from app.schemas.contact_storage import AiStatus, ContactCategory, ContactPriority, Sentiment

logger = logging.getLogger(__name__)

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
)
_MAX_PROVIDER_DETAIL_LENGTH = 500


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


def _redact_provider_text(value: str) -> str:
    redacted_value = value
    for pattern in _SECRET_PATTERNS:
        redacted_value = pattern.sub("[redacted]", redacted_value)
    return redacted_value[:_MAX_PROVIDER_DETAIL_LENGTH]


def _extract_openai_error_details(exc: OpenAIError) -> str | None:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None) or getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    error_body = body.get("error", body) if isinstance(body, dict) else {}

    provider_code = error_body.get("code") or getattr(exc, "code", None)
    provider_type = error_body.get("type") or getattr(exc, "type", None)
    provider_message = error_body.get("message") or str(exc)

    details = []
    if status_code:
        details.append(f"status={status_code}")
    if provider_code:
        details.append(f"code={provider_code}")
    if provider_type:
        details.append(f"type={provider_type}")
    if provider_message:
        # Сообщение провайдера помогает отличить модель, проект, квоту и endpoint,
        # но перед выводом мы на всякий случай вырезаем похожие на секреты фрагменты.
        details.append(f"message={_redact_provider_text(str(provider_message))}")

    return "; ".join(details) or None


class OpenAIAnalysisService:
    def __init__(self, settings: Settings | None = None, client: OpenAI | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def analyze_comment(self, comment: str) -> AIServiceResult:
        start_time = time.perf_counter()
        logger.info(
            "event=ai_analysis_started provider=openai model=%s custom_base_url=%s comment_length=%s",
            self.settings.openai_model,
            bool(self.settings.openai_base_url),
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
        except PermissionDeniedError as exc:
            return self._fallback(
                "api_permission_denied",
                "У проекта OpenAI нет доступа к выбранной модели или операции",
                exc,
            )
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
            client_kwargs = {
                "api_key": self.settings.openai_api_key,
                "timeout": self.settings.openai_timeout_seconds,
                "max_retries": self.settings.openai_max_retries,
            }
            if self.settings.openai_base_url:
                # ProxyAPI и другие совместимые шлюзы подключаются заменой base_url,
                # без переписывания бизнес-логики AI-сервиса.
                client_kwargs["base_url"] = self.settings.openai_base_url
            self._client = OpenAI(
                **client_kwargs,
            )
        return self._client

    def _fallback(
        self,
        error_code: str,
        error_message: str,
        exc: Exception | None = None,
    ) -> AIServiceResult:
        provider_details = _extract_openai_error_details(exc) if isinstance(exc, OpenAIError) else None
        safe_error_message = (
            f"{error_message}. Детали OpenAI: {provider_details}"
            if provider_details
            else error_message
        )
        logger.warning(
            "event=ai_fallback_applied reason=%s error_type=%s provider_details=%s fallback_applied=true",
            error_code,
            type(exc).__name__ if exc else None,
            provider_details,
        )
        return build_fallback_result(error_code=error_code, error_message=safe_error_message)


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
            suggested_reply=(
                "Здравствуйте! Да, такой MVP можно реализовать. Для предварительной оценки мне нужно уточнить "
                "количество ролей пользователей, сценарии работы с заявками, состав полей формы, правила статусов, "
                "виды email-уведомлений и требования к AI-классификации. Также важно понять, нужна ли "
                "административная панель, авторизация и где планируется размещать сервис. После этого можно будет "
                "определить состав первой версии и подготовить ориентир по срокам и стоимости."
            ),
        )

    def analyze_comment(self, comment: str) -> AIServiceResult:
        if self.mode == "error":
            raise RuntimeError("Тестовая ошибка fake AI")
        if self.mode == "fallback":
            return build_fallback_result("fake_fallback", "Fake fallback")
        return AIServiceResult(analysis=self.analysis, status=AiStatus.SUCCESS)
