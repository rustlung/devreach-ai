# Тест-план DevReach AI

## Цель тестирования

Проверить, что фундамент FastAPI-проекта запускается локально, корректно читает настройки, проверяет SQLite, пишет логи и возвращает безопасные API-ошибки без внешних сервисов.

## Виды тестирования

- Unit-тесты конфигурации и изолированных компонентов.
- Integration-тесты FastAPI endpoint, middleware и обработчиков ошибок.
- Ручные CLI-проверки фундамента.

## Тестовое окружение

- Python 3.12.
- Локальная `.venv`.
- SQLite-файлы только локальные или временные.
- OpenAI, Resend, интернет и production-база не используются.

## Автоматические сценарии

### HEALTH-001

Успешный `GET /api/health` возвращает `status=ok`, имя сервиса, версию и `database=available`.

Файл теста: `tests/integration/test_health.py`.

### HEALTH-002

При недоступной SQLite БД `GET /api/health` возвращает HTTP 503, безопасное сообщение и не раскрывает traceback.

Файл теста: `tests/integration/test_health.py`.

### CONFIG-001

Настройки загружаются из переменных окружения, CORS origins разбираются из строки, уровень логирования нормализуется.

Файл теста: `tests/unit/test_config.py`.

### LOGGING-001

HTTP-запрос получает `X-Request-ID` в ответе.

Файл теста: `tests/integration/test_logging.py`.

### LOGGING-002

Завершение HTTP-запроса фиксируется в логах с request ID.

Файл теста: `tests/integration/test_logging.py`.

### ERROR-001

Необработанная ошибка возвращает единый безопасный ответ без внутренних деталей.

Файл теста: `tests/integration/test_errors.py`.

## Ручные сценарии

- Выполнить `alembic upgrade head` из корня проекта.
- Выполнить `python -m app.cli check-foundation`.
- При необходимости запустить `uvicorn app.main:app --reload` и открыть `/docs`.
- Выполнить `GET /api/health` через браузер или HTTP-клиент.

## Таблица соответствия

| ID | Сценарий | Тип | Автоматизирован | Файл теста | Пройдено |
| -- | -------- | --- | --------------- | ---------- | -------- |
| HEALTH-001 | Успешный health check | Integration | Да | `tests/integration/test_health.py` | [x] |
| HEALTH-002 | Health check при недоступной БД | Integration | Да | `tests/integration/test_health.py` | [x] |
| CONFIG-001 | Настройки загружаются из окружения | Unit | Да | `tests/unit/test_config.py` | [x] |
| LOGGING-001 | HTTP-запрос получает request ID | Integration | Да | `tests/integration/test_logging.py` | [x] |
| LOGGING-002 | Завершение запроса фиксируется в логах | Integration | Да | `tests/integration/test_logging.py` | [x] |
| ERROR-001 | Необработанная ошибка возвращает безопасный ответ | Integration | Да | `tests/integration/test_errors.py` | [x] |

## Финальный checklist перед сдачей проекта

- [ ] Все автоматические тесты пройдены.
- [ ] Ручной health check выполнен.
- [ ] Миграции применяются из чистого состояния.
- [ ] OpenAI live-вызов выполнен только при явном разрешении.
- [ ] Реальное тестовое письмо отправлено только при явном разрешении.
- [ ] Секреты отсутствуют в репозитории.
- [ ] README финального этапа описывает запуск, API, деплой и ограничения.
