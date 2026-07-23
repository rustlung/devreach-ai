from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.rate_limiter import SlidingWindowRateLimiter
from tests.conftest import readable_test_id


class MutableClock:
    def __init__(self, value: float = 1_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


@readable_test_id("первые запросы в пределах лимита разрешены")
def test_first_requests_are_allowed(_case_id) -> None:
    """RATE-LIMIT-UNIT-001: первые запросы в пределах лимита разрешаются."""
    limiter = SlidingWindowRateLimiter(limit=3, window_seconds=60, clock=MutableClock())

    decisions = [limiter.check("client-a") for _ in range(3)]

    assert [decision.allowed for decision in decisions] == [True, True, True]
    assert decisions[-1].remaining == 0


@readable_test_id("запрос сверх лимита отклоняется")
def test_request_over_limit_is_rejected(_case_id) -> None:
    """RATE-LIMIT-UNIT-002: запрос сверх лимита отклоняется."""
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60, clock=MutableClock())

    limiter.check("client-a")
    limiter.check("client-a")
    decision = limiter.check("client-a")

    assert decision.allowed is False
    assert decision.retry_after_seconds == 60


@readable_test_id("после окончания окна запрос снова разрешен")
def test_request_is_allowed_after_window_expires(_case_id) -> None:
    """RATE-LIMIT-WINDOW-001: после окончания sliding window запрос снова разрешается."""
    clock = MutableClock()
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60, clock=clock)
    limiter.check("client-a")

    clock.advance(61)
    decision = limiter.check("client-a")

    assert decision.allowed is True
    assert decision.remaining == 0


@readable_test_id("старые записи удаляются лениво")
def test_old_records_are_cleaned_lazily(_case_id) -> None:
    """RATE-LIMIT-CLEANUP-001: старые timestamps удаляются при новых проверках."""
    clock = MutableClock()
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60, clock=clock)
    limiter.check("client-a")

    clock.advance(61)
    limiter.check("client-b")

    assert limiter.stored_client_count() == 1


@readable_test_id("разные клиенты имеют независимые лимиты")
def test_different_clients_have_independent_limits(_case_id) -> None:
    """RATE-LIMIT-INDEPENDENT-IP-001: лимит одного client key не блокирует другой."""
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60, clock=MutableClock())
    limiter.check("client-a")

    first_client = limiter.check("client-a")
    second_client = limiter.check("client-b")

    assert first_client.allowed is False
    assert second_client.allowed is True


@readable_test_id("неизвестный клиент обрабатывается предсказуемо")
def test_unknown_client_key_is_handled_predictably(_case_id) -> None:
    """RATE-LIMIT-UNKNOWN-001: unknown client key получает обычный лимит."""
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60, clock=MutableClock())

    first = limiter.check("ip_sha256:unknown")
    second = limiter.check("ip_sha256:unknown")

    assert first.allowed is True
    assert second.allowed is False


@readable_test_id("retry after рассчитывается по первому активному запросу")
def test_retry_after_is_calculated_from_oldest_active_hit(_case_id) -> None:
    """RATE-LIMIT-RETRY-AFTER-001: retry_after считается до выхода старейшего запроса из окна."""
    clock = MutableClock()
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60, clock=clock)
    limiter.check("client-a")
    clock.advance(10)
    limiter.check("client-a")
    clock.advance(5)

    decision = limiter.check("client-a")

    assert decision.allowed is False
    assert decision.retry_after_seconds == 45


@readable_test_id("очистка не ломает активные записи")
def test_cleanup_keeps_active_records(_case_id) -> None:
    """RATE-LIMIT-CLEANUP-002: очистка старых записей не удаляет активные timestamps."""
    clock = MutableClock()
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60, clock=clock)
    limiter.check("client-a")
    clock.advance(30)
    limiter.check("client-a")
    clock.advance(31)

    decision = limiter.check("client-a")

    assert decision.allowed is True
    assert limiter.check("client-a").allowed is False


@readable_test_id("параллельные проверки не превышают лимит")
def test_parallel_checks_do_not_exceed_limit(_case_id) -> None:
    """RATE-LIMIT-CONCURRENCY-001: lock защищает счётчик при параллельных запросах."""
    limiter = SlidingWindowRateLimiter(limit=5, window_seconds=60, clock=MutableClock())

    with ThreadPoolExecutor(max_workers=10) as executor:
        decisions = list(executor.map(lambda _: limiter.check("client-a"), range(20)))

    assert sum(decision.allowed for decision in decisions) == 5
    assert sum(not decision.allowed for decision in decisions) == 15


@pytest.mark.parametrize(
    ("limit", "window_seconds"),
    [(0, 60), (3, 0), (-1, 60), (3, -1)],
    ids=[
        "нулевое количество запросов отклоняется",
        "нулевое окно отклоняется",
        "отрицательное количество запросов отклоняется",
        "отрицательное окно отклоняется",
    ],
)
def test_invalid_limiter_configuration_is_rejected(limit: int, window_seconds: int) -> None:
    """RATE-LIMIT-CONFIG-001: некорректная конфигурация limiter отклоняется."""
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(limit=limit, window_seconds=window_seconds)
