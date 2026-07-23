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

Успешный `GET /api/health` возвращает `status=ok` или `status=degraded`, имя сервиса, версию, environment, latency БД и статусы конфигурации integrations.

Файл теста: `tests/integration/test_health.py`.

### HEALTH-002

При недоступной SQLite БД `GET /api/health` возвращает HTTP 503, `status=unavailable`, безопасное сообщение и не раскрывает traceback.

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

## Автоматические сценарии этапа 2

Ограничения этапа 2: имя 2-80 символов; телефон 8-15 цифр после нормализации; email до 254 символов; комментарий 5-5000 символов. Все проверки выполняются без FastAPI endpoint, БД, OpenAI, email и интернет-запросов.

| ID | Сценарий | Предусловия | Входные данные | Ожидаемый результат | Тип теста | Автоматический тест | Файл теста |
| -- | -------- | ----------- | -------------- | ------------------- | -------- | ------------------- | ---------- |
| NORMALIZATION-001 | Однострочный текст очищается и схлопывает пробелы | Нет | `   Иван    Иванов   ` | `Иван Иванов` | Unit | `test_single_line_text_is_normalized` | `tests/unit/test_normalizers.py` |
| NORMALIZATION-002 | Переводы строк в однострочном поле становятся пробелом | Нет | `Анна\nМария` | `Анна Мария` | Unit | `test_single_line_text_is_normalized` | `tests/unit/test_normalizers.py` |
| NORMALIZATION-EMAIL-001 | Email очищается и приводится к нижнему регистру | Нет | `User@Example.COM` | `user@example.com` | Unit | `test_email_is_normalized` | `tests/unit/test_normalizers.py` |
| NORMALIZATION-PHONE-001 | Российский телефон с `8` приводится к `+7` | Нет | `8 (999) 123-45-67` | `+79991234567` | Unit | `test_phone_is_normalized` | `tests/unit/test_normalizers.py` |
| NORMALIZATION-PHONE-002 | Российский телефон с `+7` очищается | Нет | `+7 999 123 45 67` | `+79991234567` | Unit | `test_phone_is_normalized` | `tests/unit/test_normalizers.py` |
| NORMALIZATION-PHONE-003 | Международный телефон сохраняет код страны | Нет | `+49 30 123456` | `+4930123456` | Unit | `test_phone_is_normalized` | `tests/unit/test_normalizers.py` |
| NORMALIZATION-PHONE-004 | Телефон очищается от пробелов по краям | Нет | `  +7 999 123 45 67  ` | `+79991234567` | Unit | `test_phone_is_normalized` | `tests/unit/test_normalizers.py` |
| NORMALIZATION-COMMENT-001 | Комментарий очищается только по краям | Нет | `   Первая строка.\n\nВторая    строка.   ` | Внутренние пробелы и абзацы сохранены | Unit | `test_multiline_text_keeps_internal_formatting` | `tests/unit/test_normalizers.py` |
| VALIDATION-PHONE-001 | Нормализатор отклоняет буквы в телефоне | Нет | `phone text` | `ValueError` | Unit | `test_phone_normalizer_rejects_forbidden_characters` | `tests/unit/test_normalizers.py` |
| VALIDATION-PHONE-002 | Нормализатор отклоняет посторонний спецсимвол | Нет | `+7 999 123 * 45` | `ValueError` | Unit | `test_phone_normalizer_rejects_forbidden_characters` | `tests/unit/test_normalizers.py` |
| VALIDATION-NAME-001 | Обычное русское имя допустимо | Валидные остальные поля | `Иван` | Схема создана | Unit | `test_valid_name_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-002 | Имя и фамилия допустимы | Валидные остальные поля | `Иван Иванов` | Схема создана | Unit | `test_valid_name_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-003 | Повторяющиеся пробелы в имени схлопываются | Валидные остальные поля | `   Иван    Иванов   ` | `Иван Иванов` | Unit | `test_valid_name_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-004 | Дефис в имени допустим | Валидные остальные поля | `Анна-Мария` | Схема создана | Unit | `test_valid_name_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-005 | Апостроф в имени допустим | Валидные остальные поля | `O'Connor` | Схема создана | Unit | `test_valid_name_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-006 | Латинское имя допустимо | Валидные остальные поля | `Jean-Pierre` | Схема создана | Unit | `test_valid_name_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-007 | Несколько частей имени допустимы | Валидные остальные поля | `Мария де Ла Крус` | Схема создана | Unit | `test_valid_name_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-008 | Цифра в имени запрещена | Валидные остальные поля | `Иван123` | Ошибка про цифры | Unit | `test_invalid_name_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-009 | Подчёркивание в имени запрещено | Валидные остальные поля | `user_name` | Ошибка про спецсимволы | Unit | `test_invalid_name_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-010 | `@` в имени запрещён | Валидные остальные поля | `Иван@` | Ошибка про спецсимволы | Unit | `test_invalid_name_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-011 | Имя только из пробелов запрещено | Валидные остальные поля | пробелы | Ошибка длины | Unit | `test_invalid_name_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-012 | Слишком короткое имя запрещено | Валидные остальные поля | `A` | Ошибка длины | Unit | `test_invalid_name_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-013 | Слишком длинное имя запрещено | Валидные остальные поля | 81 символ | Ошибка длины | Unit | `test_invalid_name_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-014 | Разделители подряд запрещены | Валидные остальные поля | `Иван--Петров` | Ошибка про разделители | Unit | `test_invalid_name_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-015 | Разделитель в начале запрещён | Валидные остальные поля | `-Иван` | Ошибка про начало | Unit | `test_invalid_name_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-016 | Разделитель в конце запрещён | Валидные остальные поля | `Иван-` | Ошибка про конец | Unit | `test_invalid_name_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-NAME-017 | Разделитель рядом с пробелом запрещён | Валидные остальные поля | `Иван  -  Петров` | Ошибка про разделители | Unit | `test_invalid_name_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-PHONE-003 | Российский телефон с `8` принимается | Валидные остальные поля | `8 (999) 123-45-67` | `+79991234567` | Unit | `test_valid_phone_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-PHONE-004 | Российский телефон с `+7` принимается | Валидные остальные поля | `+7 999 123 45 67` | `+79991234567` | Unit | `test_valid_phone_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-PHONE-005 | Телефон со скобками и дефисами принимается | Валидные остальные поля | `+7 (999) 123-45-67` | `+79991234567` | Unit | `test_valid_phone_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-PHONE-006 | Международный телефон принимается | Валидные остальные поля | `+49 30 123456` | `+4930123456` | Unit | `test_valid_phone_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-PHONE-007 | Пробелы по краям телефона удаляются | Валидные остальные поля | `  +7 999 123 45 67  ` | `+79991234567` | Unit | `test_valid_phone_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-PHONE-008 | Буквы в телефоне запрещены | Валидные остальные поля | `+7 phone` | Ошибка символов | Unit | `test_invalid_phone_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-PHONE-009 | Спецсимволы в телефоне запрещены | Валидные остальные поля | `+7 999 123 * 45` | Ошибка символов | Unit | `test_invalid_phone_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-PHONE-010 | Слишком короткий телефон запрещён | Валидные остальные поля | `+123` | Ошибка длины | Unit | `test_invalid_phone_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-PHONE-011 | Слишком длинный телефон запрещён | Валидные остальные поля | 16 цифр | Ошибка длины | Unit | `test_invalid_phone_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-PHONE-012 | Пустой телефон запрещён | Валидные остальные поля | пустая строка | Ошибка обязательности | Unit | `test_invalid_phone_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-EMAIL-001 | Корректный email допустим | Валидные остальные поля | `user@example.com` | Схема создана | Unit | `test_valid_email_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-EMAIL-002 | Пробелы по краям email удаляются | Валидные остальные поля | `  user@example.com  ` | `user@example.com` | Unit | `test_valid_email_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-EMAIL-003 | Регистр email приводится к нижнему | Валидные остальные поля | `User@Example.COM` | `user@example.com` | Unit | `test_valid_email_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-EMAIL-004 | Внутренний пробел email запрещён | Валидные остальные поля | `user name@example.com` | Ошибка пробела | Unit | `test_invalid_email_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-EMAIL-005 | Некорректный формат email запрещён | Валидные остальные поля | `not-email` | Ошибка формата | Unit | `test_invalid_email_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-EMAIL-006 | Пустой email запрещён | Валидные остальные поля | пустая строка | Ошибка обязательности | Unit | `test_invalid_email_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-COMMENT-001 | Корректный комментарий допустим | Валидные остальные поля | текст | Схема создана | Unit | `test_valid_comment_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-COMMENT-002 | Пробелы по краям комментария удаляются | Валидные остальные поля | текст с пробелами | Края очищены | Unit | `test_valid_comment_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-COMMENT-003 | Внутренние повторяющиеся пробелы сохраняются | Валидные остальные поля | `Первая    строка.` | Пробелы сохранены | Unit | `test_valid_comment_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-COMMENT-004 | Переносы строк сохраняются | Валидные остальные поля | две строки | Перенос сохранён | Unit | `test_valid_comment_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-COMMENT-005 | Абзацы сохраняются | Валидные остальные поля | две строки через пустую | Абзац сохранён | Unit | `test_valid_comment_is_accepted` | `tests/unit/test_contact_schema.py` |
| VALIDATION-COMMENT-006 | Комментарий только из пробелов запрещён | Валидные остальные поля | пробелы | Ошибка обязательности | Unit | `test_invalid_comment_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-COMMENT-007 | Комментарий только из переносов запрещён | Валидные остальные поля | переносы | Ошибка обязательности | Unit | `test_invalid_comment_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-COMMENT-008 | Слишком короткий комментарий запрещён | Валидные остальные поля | `abc` | Ошибка длины | Unit | `test_invalid_comment_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-COMMENT-009 | Слишком длинный комментарий запрещён | Валидные остальные поля | 5001 символ | Ошибка длины | Unit | `test_invalid_comment_is_rejected` | `tests/unit/test_contact_schema.py` |
| VALIDATION-CONTACT-001 | Полностью валидное обращение создаёт схему | Нет | валидные поля | Схема создана | Unit | `test_valid_contact_request_is_created` | `tests/unit/test_contact_schema.py` |
| NORMALIZATION-CONTACT-001 | Все поля обращения возвращаются нормализованными | Нет | поля с лишними пробелами | Значения нормализованы | Unit | `test_contact_request_returns_normalized_fields` | `tests/unit/test_contact_schema.py` |
| VALIDATION-CONTACT-002 | Ошибка одного поля содержит понятную информацию | Нет | имя с цифрами | Русская причина ошибки | Unit | `test_single_field_error_contains_clear_message` | `tests/unit/test_contact_schema.py` |
| NORMALIZATION-COMMENT-002 | Внутренние пробелы комментария не изменяются | Нет | комментарий с внутренними пробелами | Пробелы сохранены | Unit | `test_comment_internal_spaces_are_not_changed` | `tests/unit/test_contact_schema.py` |
| NORMALIZATION-NAME-001 | Лишние пробелы в имени не попадают в итоговые данные | Нет | имя с лишними пробелами | `Иван Иванов` | Unit | `test_extra_name_spaces_are_not_returned` | `tests/unit/test_contact_schema.py` |
| VALIDATION-HONEYPOT-001 | Заполненный honeypot отклоняет обращение | Нет | `website` заполнен | Ошибка служебного поля | Unit | `test_filled_honeypot_is_rejected` | `tests/unit/test_contact_schema.py` |

## Автоматические сценарии этапа 3

Все проверки этапа 3 выполняются без `POST /api/contact`, OpenAI, email, frontend и production-базы. Unit-тесты репозитория используют временную SQLite через `tmp_path`; integration-тесты проверяют Alembic на отдельной временной SQLite.

| ID | Описание | Предусловия | Входные данные | Шаги | Ожидаемый результат | Тип теста | Тестовая функция | Файл теста |
| -- | -------- | ----------- | -------------- | ---- | ------------------- | -------- | ---------------- | ---------- |
| REPOSITORY-CREATE-001 | Валидное обращение создаётся и получает ID | Временная SQLite | `ContactRequestCreate` | Вызвать `create()` | Запись сохранена, ID присвоен, поля нормализованы | Unit | `test_create_contact_persists_valid_request` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-CREATE-002 | При создании выставляются начальные статусы | Временная SQLite | Валидное обращение | Вызвать `create()` | `received`, `pending`, `pending`, `pending` | Unit | `test_create_contact_sets_initial_statuses` | `tests/unit/test_contact_repository.py` |
| DATABASE-MODEL-001 | При создании устанавливаются UTC-метки | Временная SQLite | Валидное обращение | Вызвать `create()` | `created_at` и `updated_at` в UTC | Unit | `test_create_contact_sets_utc_timestamps` | `tests/unit/test_contact_repository.py` |
| DATABASE-MODEL-003 | `updated_at` меняется при обновлении | Временная SQLite | Созданное обращение | Обновить processing status | `updated_at` больше исходного значения | Unit | `test_updated_at_changes_after_update` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-GET-001 | Существующее обращение возвращается по ID | Временная SQLite | Созданное обращение | Вызвать `get_by_id()` | Возвращена модель | Unit | `test_get_by_id_returns_existing_contact` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-GET-002 | Несуществующее обращение возвращает `None` | Временная SQLite | ID 999 | Вызвать `get_by_id()` | Возвращён `None` | Unit | `test_get_by_id_returns_none_for_missing_contact` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-AI-UPDATE-001 | AI-поля сохраняются | Временная SQLite | AI update | Вызвать `update_ai_result()` | Все AI-поля обновлены | Unit | `test_update_ai_result_saves_all_ai_fields` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-AI-UPDATE-002 | AI error сохраняется | Временная SQLite | `ai_status=failed`, error | Вызвать `update_ai_result()` | Статус и ошибка сохранены | Unit | `test_update_ai_result_can_save_error` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-AI-UPDATE-003 | AI-обновление не меняет исходные данные | Временная SQLite | Созданное обращение | Обновить AI | Name/phone/email/comment не изменены | Unit | `test_update_ai_result_does_not_change_original_fields` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-AI-UPDATE-004 | AI-обновление отсутствующего ID отклоняется | Временная SQLite | ID 999 | Вызвать `update_ai_result()` | `ContactNotFoundError` | Unit | `test_update_ai_result_rejects_missing_contact` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-EMAIL-UPDATE-001 | Статус письма владельцу обновляется отдельно | Временная SQLite | `owner=failed`, error | Вызвать `update_owner_email_status()` | Owner email status и error сохранены | Unit | `test_update_owner_email_status_updates_only_owner` | `tests/unit/test_contact_repository.py` |
| EMAIL-OWNER-ONLY-001 | Общий update email-статуса работает только для владельца | Временная SQLite | `owner=sent` | Вызвать `update_email_statuses()` | User email fields отсутствуют | Unit | `test_update_email_statuses_updates_owner_only` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-STATUS-001 | Общий статус обработки обновляется отдельно | Временная SQLite | `completed` | Вызвать `update_processing_status()` | Остальные поля не изменены | Unit | `test_update_processing_status_changes_only_processing_status` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-METRICS-001 | Пустая база возвращает нулевые метрики | Пустая SQLite | Нет | Вызвать `get_metrics()` | Все агрегаты пустые/нулевые | Unit | `test_get_metrics_returns_zero_values_for_empty_database` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-METRICS-002 | Несколько записей корректно агрегируются | Временная SQLite | 2 обращения с разными статусами | Вызвать `get_metrics()` | Счётчики по статусам и категориям корректны | Unit | `test_get_metrics_aggregates_multiple_contacts` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-METRICS-003 | Метрики не содержат персональные данные | Временная SQLite | Валидное обращение | Проверить результат `get_metrics()` | Нет имени, email, телефона, комментария | Unit | `test_get_metrics_does_not_return_personal_data` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-ROLLBACK-001 | Ошибка сохранения выполняет rollback | Временная SQLite | Контролируемая ошибка commit | Вызвать `create()` | Rollback выполнен, сессия пригодна дальше | Unit | `test_create_rolls_back_after_database_error` | `tests/unit/test_contact_repository.py` |
| DATABASE-MIGRATION-001 | Alembic upgrade создаёт таблицу обращений | Временная SQLite | Миграции Alembic | `upgrade head` | Таблица и ключевые поля созданы | Integration | `test_alembic_upgrade_creates_contact_requests_table` | `tests/integration/test_database.py` |
| DATABASE-MODEL-002 | Модель совместима с актуальной миграцией | Временная SQLite после миграции | Валидное обращение | Создать через repository | Запись создаётся и читается | Integration | `test_repository_works_with_migrated_database` | `tests/integration/test_database.py` |
| DATABASE-MIGRATION-002 | Alembic downgrade возвращает legacy user email поля | Временная SQLite | Миграции Alembic | `upgrade head`, `downgrade -1` | `user_email_status` и `user_email_error` возвращены | Integration | `test_alembic_downgrade_restores_user_email_fields` | `tests/integration/test_database.py` |
| DATABASE-REMOVE-USER-EMAIL-FIELDS-001 | Актуальный upgrade удаляет legacy user email поля | Временная SQLite | Миграции Alembic | `upgrade head`, `downgrade -1`, `upgrade head` | На `head` user email fields отсутствуют | Integration | `test_alembic_downgrade_then_upgrade_removes_user_email_fields_again` | `tests/integration/test_database.py` |

## Автоматические сценарии этапа 4

Все автоматические проверки AI-сервиса выполняются без реальных внешних запросов и без расхода токенов. OpenAI SDK используется только через mock/fake-клиенты.

| ID | Описание | Предусловия | Входные данные | Шаги | Ожидаемый результат | Тип теста | Тестовая функция | Файл теста |
| -- | -------- | ----------- | -------------- | ---- | ------------------- | -------- | ---------------- | ---------- |
| AI-SCHEMA-001 | Валидный AI-результат принимается | Нет | Валидный payload | Создать `AIAnalysisResult` | Схема создана | Unit | `test_valid_ai_result_is_accepted` | `tests/unit/test_ai_schemas.py` |
| AI-SCHEMA-002 | Неизвестные enum-значения отклоняются | Нет | Unknown sentiment/category/priority | Создать `AIAnalysisResult` | `ValidationError` | Unit | `test_unknown_enum_values_are_rejected` | `tests/unit/test_ai_schemas.py` |
| AI-SCHEMA-003 | Слишком длинный summary отклоняется | Нет | 501 символ | Создать `AIAnalysisResult` | `ValidationError` | Unit | `test_too_long_summary_is_rejected` | `tests/unit/test_ai_schemas.py` |
| AI-SCHEMA-004 | Пустой suggested reply отклоняется | Нет | Пробелы | Создать `AIAnalysisResult` | `ValidationError` | Unit | `test_empty_suggested_reply_is_rejected` | `tests/unit/test_ai_schemas.py` |
| AI-SCHEMA-005 | Fallback analysis соответствует схеме | Нет | Нет | Вызвать `build_fallback_analysis()` | Нейтральный безопасный результат | Unit | `test_fallback_analysis_matches_schema` | `tests/unit/test_ai_schemas.py` |
| AI-SCHEMA-006 | Fallback service result содержит статус | Нет | Error code | Вызвать `build_fallback_result()` | `status=fallback` | Unit | `test_fallback_service_result_has_fallback_status` | `tests/unit/test_ai_schemas.py` |
| AI-SUCCESS-001 | Валидный structured output возвращает success | Mock OpenAI client | Тестовый комментарий | Вызвать `analyze_comment()` | `status=success` | Unit | `test_openai_service_returns_success_for_valid_structured_output` | `tests/unit/test_ai_service.py` |
| AI-SUCCESS-002 | Системный промпт и комментарий передаются отдельно | Mock OpenAI client | Тестовый комментарий | Проверить messages | System/user разделены | Unit | `test_openai_service_sends_system_prompt_and_user_comment_separately` | `tests/unit/test_ai_service.py` |
| AI-SUCCESS-003 | Project request для оценки передаётся отдельно и не меняет structured output | Mock OpenAI client | Комментарий о MVP и предварительной оценке | Проверить messages и `response_format` | Комментарий user message, `AIAnalysisResult` прежний | Unit | `test_project_estimate_comment_is_sent_as_user_message_without_changing_schema` | `tests/unit/test_ai_service.py` |
| AI-LOGGING-001 | Полный комментарий не попадает в логи | Mock OpenAI client | Тестовый комментарий | Проверить caplog | Комментария нет, enum есть | Unit | `test_openai_service_does_not_log_full_comment` | `tests/unit/test_ai_service.py` |
| AI-FALLBACK-NO-KEY-001 | Fallback при отсутствии API-ключа | Mock client не должен вызываться | Нет ключа | Вызвать `analyze_comment()` | `missing_api_key` | Unit | `test_openai_service_returns_fallback_before_client_call` | `tests/unit/test_ai_service.py` |
| AI-FALLBACK-DISABLED-001 | Fallback при отключённых live-вызовах | Mock client не должен вызываться | `AI_LIVE_REQUESTS_ENABLED=false` | Вызвать `analyze_comment()` | `live_requests_disabled` | Unit | `test_openai_service_returns_fallback_before_client_call` | `tests/unit/test_ai_service.py` |
| AI-FALLBACK-TIMEOUT-001 | Fallback при timeout OpenAI | Mock exception | `APITimeoutError` | Вызвать `analyze_comment()` | `api_timeout` | Unit | `test_openai_service_returns_fallback_for_provider_errors` | `tests/unit/test_ai_service.py` |
| AI-FALLBACK-CONNECTION-001 | Fallback при ошибке соединения | Mock exception | `APIConnectionError` | Вызвать `analyze_comment()` | `api_connection_error` | Unit | `test_openai_service_returns_fallback_for_provider_errors` | `tests/unit/test_ai_service.py` |
| AI-FALLBACK-AUTH-001 | Fallback при ошибке авторизации | Mock exception | `AuthenticationError` | Вызвать `analyze_comment()` | `api_auth_error` | Unit | `test_openai_service_returns_fallback_for_provider_errors` | `tests/unit/test_ai_service.py` |
| AI-FALLBACK-PERMISSION-001 | Fallback при запрете доступа OpenAI/ProxyAPI | Mock exception | `PermissionDeniedError` | Вызвать `analyze_comment()` | `api_permission_denied` | Unit | `test_openai_service_returns_fallback_for_provider_errors` | `tests/unit/test_ai_service.py` |
| AI-FALLBACK-PERMISSION-002 | Детали запрета доступа безопасно сохраняются | Mock exception с body | `PermissionDeniedError` с code/type/message | Вызвать `analyze_comment()` | В error message есть status/code/type, секреты скрыты | Unit | `test_openai_service_includes_safe_provider_details_for_permission_denied` | `tests/unit/test_ai_service.py` |
| AI-FALLBACK-RATE-LIMIT-001 | Fallback при rate limit | Mock exception | `RateLimitError` | Вызвать `analyze_comment()` | `api_rate_limit` | Unit | `test_openai_service_returns_fallback_for_provider_errors` | `tests/unit/test_ai_service.py` |
| AI-FALLBACK-API-001 | Fallback при общей API-ошибке | Mock exception | `APIError` | Вызвать `analyze_comment()` | `api_error` | Unit | `test_openai_service_returns_fallback_for_provider_errors` | `tests/unit/test_ai_service.py` |
| AI-FALLBACK-INVALID-RESPONSE-001 | Fallback при невалидном structured output | Mock response | Unknown enum | Вызвать `analyze_comment()` | `invalid_structured_output` | Unit | `test_openai_service_returns_fallback_for_invalid_response` | `tests/unit/test_ai_service.py` |
| AI-FALLBACK-EMPTY-001 | Fallback при пустом ответе | Mock response | `parsed=None` | Вызвать `analyze_comment()` | `empty_response` | Unit | `test_openai_service_returns_fallback_for_invalid_response` | `tests/unit/test_ai_service.py` |
| AI-FALLBACK-UNEXPECTED-001 | Fallback при неожиданной ошибке | Mock exception | `RuntimeError` | Вызвать `analyze_comment()` | `unexpected_error` | Unit | `test_openai_service_returns_fallback_for_unexpected_error` | `tests/unit/test_ai_service.py` |
| AI-PROMPT-SUGGESTED-REPLY-001 | System prompt требует содержательный suggested reply от первого лица | Нет | System prompt | Проверить обязательные фрагменты | Есть запреты "мы"/"свяжитесь с нами", требование деталей и уточнений | Unit | `test_system_prompt_defines_personal_suggested_reply_rules` | `tests/unit/test_ai_service.py` |
| AI-PROMPT-PROJECT-REQUEST-001 | System prompt задаёт поведение для project_request | Нет | System prompt | Проверить блок project_request | Есть прямой ответ про реализуемость и уточнения для оценки | Unit | `test_system_prompt_defines_project_request_reply_behavior` | `tests/unit/test_ai_service.py` |
| AI-PROMPT-INJECTION-001 | Prompt injection остаётся пользовательскими данными | Mock OpenAI client | Инъекционный комментарий | Проверить messages и prompt | Комментарий не склеен с system prompt | Unit | `test_prompt_injection_comment_is_not_concatenated_into_system_prompt` | `tests/unit/test_ai_service.py` |
| AI-FAKE-001 | Fake success возвращает результат | Нет | Тестовый комментарий | Вызвать fake service | `status=success` | Unit | `test_fake_service_returns_success` | `tests/unit/test_ai_service.py` |
| AI-FAKE-002 | Fake fallback возвращает fallback | Нет | Тестовый комментарий | Вызвать fake service | `status=fallback` | Unit | `test_fake_service_returns_fallback` | `tests/unit/test_ai_service.py` |
| AI-FAKE-003 | Fake error имитирует исключение | Нет | Тестовый комментарий | Вызвать fake service | `RuntimeError` | Unit | `test_fake_service_can_raise_error` | `tests/unit/test_ai_service.py` |
| AI-FAKE-004 | Fake service не создаёт OpenAI-клиент | OpenAI constructor заменён ошибкой | Тестовый комментарий | Вызвать fake service | Клиент не создан | Unit | `test_fake_service_does_not_create_openai_client` | `tests/unit/test_ai_service.py` |
| AI-FAKE-005 | Fake project_request содержит персональный полезный suggested reply | Нет | Комментарий о MVP и предварительной оценке | Вызвать fake service | Нет "мы"/"свяжитесь с нами", есть реализуемость и список уточнений | Unit | `test_fake_project_request_suggested_reply_is_specific_and_personal` | `tests/unit/test_ai_service.py` |
| AI-PROXY-001 | OpenAI SDK получает custom base_url | Mock OpenAI constructor | `OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1` | Вызвать `analyze_comment()` | Клиент создан с `base_url` | Unit | `test_openai_client_is_created_with_custom_base_url` | `tests/unit/test_ai_service.py` |

## Ручные сценарии этапа 4

| ID | Сценарий | Предусловия | Команда | Ожидаемый результат | Пройдено |
| -- | -------- | ----------- | ------- | ------------------- | -------- |
| AI-LIVE-001 | Один контролируемый live-запрос через ProxyAPI | ключ ProxyAPI задан в `OPENAI_API_KEY`, `OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1`, `AI_LIVE_REQUESTS_ENABLED=true`, пользователь явно запускает команду | `python -m app.cli analyze-comment --live` | Один structured-output ответ без прямого OpenAI API | [x] |

## Автоматические сценарии этапа 5

Все проверки этапа 5 выполняются без `POST /api/contact`, OpenAI, сохранения email-статусов в БД и реальной отправки писем. Resend SDK в unit-тестах замокан.

| ID | Описание | Предусловия | Входные данные | Шаги | Ожидаемый результат | Тип теста | Тестовая функция | Файл теста |
| -- | -------- | ----------- | -------------- | ---- | ------------------- | -------- | ---------------- | ---------- |
| EMAIL-SCHEMA-001 | Валидное email-сообщение принимается | Нет | `EmailMessage` | Создать схему | Схема создана | Unit | `test_valid_email_message_is_accepted` | `tests/unit/test_email_schemas.py` |
| EMAIL-SCHEMA-002 | Невалидные поля письма отклоняются | Нет | пустой to, неверный email, пустые subject/html/text | Создать схему | `ValidationError` | Unit | `test_invalid_email_message_fields_are_rejected` | `tests/unit/test_email_schemas.py` |
| EMAIL-SCHEMA-003 | Валидный результат отправки принимается | Нет | `EmailSendResult(status=sent)` | Создать схему | Схема создана | Unit | `test_valid_email_send_result_is_accepted` | `tests/unit/test_email_schemas.py` |
| EMAIL-SCHEMA-004 | Неизвестный email-статус отклоняется | Нет | `status=unknown` | Создать схему | `ValidationError` | Unit | `test_unknown_email_status_is_rejected` | `tests/unit/test_email_schemas.py` |
| EMAIL-RENDER-OWNER-001 | Письмо владельцу рендерится | Тестовый контекст | Контакт и AI summary | Построить owner message | HTML/text не пустые, данные есть | Unit | `test_owner_notification_is_rendered` | `tests/unit/test_email_templates.py` |
| EMAIL-NO-USER-AUTOREPLY-001 | Автоматическое письмо пользователю не предусмотрено | Тестовый email-сервис | Нет | Проверить отсутствие user methods/templates | Методы и шаблоны user confirmation отсутствуют | Unit | `test_user_confirmation_templates_are_removed`, `test_user_confirmation_methods_are_not_available` | `tests/unit/test_email_templates.py`, `tests/unit/test_email_service.py` |
| EMAIL-RENDER-OPTIONAL-001 | Optional-поля не выводят `None` | Контекст без optional | Нет summary/category/status | Построить owner message | Строка `None` отсутствует | Unit | `test_missing_optional_fields_do_not_render_none` | `tests/unit/test_email_templates.py` |
| EMAIL-HTML-ESCAPE-001 | HTML комментария экранируется | Тестовый контекст | `<script>alert("xss")</script>` | Построить owner message | Тег не исполняется, текст экранирован | Unit | `test_user_html_in_comment_is_escaped` | `tests/unit/test_email_templates.py` |
| EMAIL-TEXT-001 | Переносы строк сохраняются | Тестовый контекст | многострочный комментарий | Построить owner message | Text хранит переносы, HTML использует `pre-wrap` | Unit | `test_comment_line_breaks_are_preserved` | `tests/unit/test_email_templates.py` |
| EMAIL-HTML-ESCAPE-002 | Suggested reply экранируется | Тестовый контекст | `<script>` в suggested_reply | Построить user message | HTML экранирован | Unit | `test_user_suggested_reply_is_escaped` | `tests/unit/test_email_templates.py` |
| EMAIL-RENDER-FALLBACK-001 | AI fallback отображается в письме владельцу | Тестовый контекст | `ai_status=fallback` | Построить owner message | Владелец видит fallback, provider error не раскрывается | Unit | `test_ai_fallback_is_rendered_safely` | `tests/unit/test_email_templates.py` |
| EMAIL-SEND-PAYLOAD-001 | Payload Resend формируется корректно | Mock Resend | `EmailMessage` | Вызвать `send()` | from/to/subject/html/text/reply_to корректны | Unit | `test_resend_payload_is_built_correctly` | `tests/unit/test_email_service.py` |
| EMAIL-SEND-OWNER-001 | Уведомление владельцу отправляется на `OWNER_EMAIL` | Mock Resend | Контекст обращения | Вызвать `send_owner_notification()` | Получатель owner, reply_to пользователь | Unit | `test_owner_notification_uses_owner_email_and_user_reply_to` | `tests/unit/test_email_service.py` |
| EMAIL-OWNER-REPLY-TO-001 | Reply-To письма владельцу равен email пользователя | Mock Resend | Контекст обращения | Вызвать `send_owner_notification()` | Получатель owner, `reply_to` пользователь | Unit | `test_owner_notification_uses_owner_email_and_user_reply_to` | `tests/unit/test_email_service.py` |
| EMAIL-SEND-RESULT-001 | Успешный ответ сохраняет message id | Mock Resend | Ответ с `id` | Вызвать `send()` | `status=sent`, `message_id` сохранён | Unit | `test_successful_resend_response_returns_sent_status` | `tests/unit/test_email_service.py` |
| EMAIL-SKIPPED-DISABLED-001 | Live отключён возвращает skipped | Mock Resend | `EMAIL_LIVE_REQUESTS_ENABLED=false` | Вызвать `send()` | SDK не вызван, `status=skipped` | Unit | `test_disabled_live_requests_return_skipped` | `tests/unit/test_email_service.py` |
| EMAIL-FAILED-CONFIG-001 | Отсутствующие настройки обрабатываются | Mock Resend | нет ключа/sender/owner | Вызвать send-методы | `status=failed`, конкретный error_code | Unit | `test_missing_email_settings_are_handled` | `tests/unit/test_email_service.py` |
| EMAIL-FAILED-CONFIG-002 | Sender с именем в `EMAIL_FROM_ADDRESS` отклоняется до Resend SDK | Mock Resend | `EMAIL_FROM_ADDRESS=Name <onboarding@resend.dev>` | Вызвать `send()` | `invalid_sender`, внешний вызов не выполнен | Unit | `test_missing_email_settings_are_handled` | `tests/unit/test_email_service.py` |
| EMAIL-FAILED-PROVIDER-001 | Ошибки Resend классифицируются | Mock Resend | auth/rate/timeout/connection/runtime | Вызвать `send()` | `status=failed`, безопасный error_code | Unit | `test_provider_errors_return_failed` | `tests/unit/test_email_service.py` |
| EMAIL-FAILED-INVALID-RESPONSE-001 | Ответ без id считается ошибкой | Mock Resend | `{}` | Вызвать `send()` | `invalid_provider_response` | Unit | `test_invalid_provider_response_returns_failed` | `tests/unit/test_email_service.py` |
| EMAIL-LOGGING-001 | Тело письма и PII не попадают в логи | Mock logger | email/body | Вызвать `send()` | В логах нет body и email | Unit | `test_email_body_and_personal_data_are_not_logged` | `tests/unit/test_email_service.py` |
| EMAIL-FAKE-001 | Fake-сервис поддерживает статусы | Нет | success/failed/skipped | Вызвать fake `send()` | Статусы корректны, сообщения сохранены | Unit | `test_fake_email_service_modes` | `tests/unit/test_email_service.py` |
| EMAIL-FAKE-002 | Fake exception имитирует ошибку | Нет | `mode=error` | Вызвать fake `send()` | `RuntimeError` | Unit | `test_fake_email_service_can_raise_error` | `tests/unit/test_email_service.py` |
| EMAIL-FAKE-003 | Fake-сервис не вызывает Resend | Resend send заменён ошибкой | `EmailMessage` | Вызвать fake `send()` | Resend не вызван | Unit | `test_fake_email_service_does_not_call_resend` | `tests/unit/test_email_service.py` |

## Ручные сценарии этапа 5

| ID | Сценарий | Предусловия | Команда | Ожидаемый результат | Пройдено |
| -- | -------- | ----------- | ------- | ------------------- | -------- |
| EMAIL-LIVE-001 | Одно контролируемое live-письмо через Resend | `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS`, `EMAIL_LIVE_REQUESTS_ENABLED=true`, явный получатель | `python -m app.cli check-email --live --recipient test@example.com` | Отправлено одно тестовое письмо или безопасная ошибка без раскрытия секретов | [ ] |

## Автоматические сценарии этапа 6

Все проверки этапа 6 выполняются с fake AI/email или замоканными ошибками. Реальные OpenAI и Resend не вызываются.

| ID | Описание | Предусловия | Входные данные | Шаги | Ожидаемый результат | Тип теста | Тестовая функция | Файл теста |
| -- | -------- | ----------- | -------------- | ---- | ------------------- | -------- | ---------------- | ---------- |
| PIPELINE-SUCCESS-001 | Полный pipeline успешно завершается | Временная SQLite, fake AI/email | Валидное обращение | Вызвать `ContactService.process_contact()` | Запись, AI, owner email и `completed` сохранены | Unit | `test_contact_service_processes_full_success` | `tests/unit/test_contact_service.py` |
| PIPELINE-AI-FALLBACK-001 | AI fallback не останавливает pipeline | Временная SQLite, fake AI fallback | Валидное обращение | Вызвать service | `ai_status=fallback`, письма отправлены, `completed_with_errors` | Unit | `test_contact_service_continues_after_ai_fallback` | `tests/unit/test_contact_service.py` |
| PIPELINE-AI-EXCEPTION-001 | Исключение AI превращается в fallback | Временная SQLite, AI raises | Валидное обращение | Вызвать service | Fallback сохранён, email-этап продолжается | Unit | `test_contact_service_converts_ai_exception_to_fallback` | `tests/unit/test_contact_service.py` |
| PIPELINE-OWNER-EMAIL-FAILED-001 | Ошибка письма владельцу даёт частичный успех | Временная SQLite, owner failed | Валидное обращение | Вызвать service | owner `failed`, `completed_with_errors` | Unit | `test_owner_email_failure_results_in_completed_with_errors` | `tests/unit/test_contact_service.py` |
| PIPELINE-SINGLE-EMAIL-001 | Pipeline отправляет ровно одно письмо владельцу | Временная SQLite, fake services | Валидное обращение | Вызвать service | Одно письмо `owner_notification`, user autoreply отсутствует | Unit | `test_contact_service_sends_single_owner_email_without_user_autoreply` | `tests/unit/test_contact_service.py` |
| PIPELINE-EMAILS-FAILED-001 | Ошибка письма владельцу не удаляет AI-результат | Временная SQLite, owner failed | Валидное обращение | Вызвать service | AI сохранён, owner `failed`, `completed_with_errors` | Unit | `test_owner_email_failure_keeps_ai_result` | `tests/unit/test_contact_service.py` |
| PIPELINE-EMAIL-SKIPPED-001 | Skipped owner email считается частичной ошибкой | Временная SQLite, owner skipped | Валидное обращение | Вызвать service | Owner email `skipped`, итог `completed_with_errors` | Unit | `test_skipped_owner_email_results_in_completed_with_errors` | `tests/unit/test_contact_service.py` |
| PIPELINE-REPOSITORY-CREATE-FAILED-001 | Ошибка create останавливает внешние этапы | Repository create raises | Валидное обращение | Вызвать service | AI/email не вызваны, service error | Unit | `test_repository_create_error_stops_external_stages` | `tests/unit/test_contact_service.py` |
| PIPELINE-REPOSITORY-UPDATE-FAILED-001 | Ошибка сохранения AI критична | Repository AI update raises | Валидное обращение | Вызвать service | Email не отправляется, service error | Unit | `test_repository_ai_update_error_stops_email` | `tests/unit/test_contact_service.py` |
| PIPELINE-REPOSITORY-EMAIL-UPDATE-FAILED-001 | Ошибка сохранения email-статуса критична | Repository email update raises | Валидное обращение | Вызвать service | Отправка могла состояться, но service error поднят | Unit | `test_repository_email_status_update_error_is_critical` | `tests/unit/test_contact_service.py` |
| PIPELINE-STATUS-001 | External errors не дают `failed` | Временная SQLite, AI fallback, email failed | Валидное обращение | Вызвать service | Итог `completed_with_errors`, не `failed` | Unit | `test_processing_failed_is_not_used_for_external_errors` | `tests/unit/test_contact_service.py` |
| CONTACT-API-SUCCESS-001 | POST `/api/contact` успешно создаёт обращение | API, временная SQLite, fake services | Валидный JSON | POST | HTTP 201, запись сохранена, статусы `sent/completed` | Integration | `test_contact_api_success_creates_contact` | `tests/integration/test_contact_api.py` |
| CONTACT-API-AI-FALLBACK-001 | API возвращает 201 при AI fallback | API, fake AI fallback | Валидный JSON | POST | `ai_processed=false`, `completed_with_errors` | Integration | `test_contact_api_ai_fallback_returns_created` | `tests/integration/test_contact_api.py` |
| CONTACT-API-EMAIL-FAILED-001 | API возвращает 201 при email failed | API, fake owner email failed | Валидный JSON | POST | Email status отражён, техошибка не раскрыта | Integration | `test_contact_api_email_failure_returns_completed_with_errors` | `tests/integration/test_contact_api.py` |
| CONTACT-API-VALIDATION-001 | Невалидные данные дают 422 | API | name/email/phone/comment/honeypot invalid | POST | Service не вызван, запись не создана | Integration | `test_contact_api_validation_errors_do_not_call_service` | `tests/integration/test_contact_api.py` |
| CONTACT-API-DATABASE-FAILED-001 | Ошибка create даёт безопасный 500 | API, failing repository | Валидный JSON | POST | HTTP 500 без traceback, email не вызван | Integration | `test_contact_api_database_create_error_returns_safe_500` | `tests/integration/test_contact_api.py` |
| CONTACT-API-REQUEST-ID-001 | Request ID совпадает в header и body | API, fake services | Валидный JSON с `X-Request-ID` | POST | Body и header содержат один request ID | Integration | `test_contact_api_success_creates_contact` | `tests/integration/test_contact_api.py` |
| CONTACT-API-OPENAPI-001 | Endpoint зарегистрирован в OpenAPI | API | Нет | GET `/openapi.json` | `POST /api/contact` и 201 задокументированы | Integration | `test_contact_api_openapi_contains_contact_endpoint` | `tests/integration/test_contact_api.py` |

## Автоматические сценарии этапа 7

Все проверки этапа 7 выполняются без реальных ProxyAPI и Resend. Unit-тесты используют управляемые часы без `sleep`, integration-тесты используют временную SQLite и fake AI/email.

| ID | Описание | Предусловия | Входные данные | Шаги | Ожидаемый результат | Тип теста | Тестовая функция | Файл теста |
| -- | -------- | ----------- | -------------- | ---- | ------------------- | -------- | ---------------- | ---------- |
| RATE-LIMIT-UNIT-001 | Первые запросы разрешены | In-memory limiter | 3 запроса одного client key | Вызвать `check()` | Все разрешены, remaining корректен | Unit | `test_first_requests_are_allowed` | `tests/unit/test_rate_limiter.py` |
| RATE-LIMIT-UNIT-002 | Запрос сверх лимита отклоняется | In-memory limiter | 3-й запрос при лимите 2 | Вызвать `check()` | `allowed=false`, retry_after есть | Unit | `test_request_over_limit_is_rejected` | `tests/unit/test_rate_limiter.py` |
| RATE-LIMIT-WINDOW-001 | После окончания окна запрос снова разрешён | Управляемые часы | Перемотка на 61 секунду | Вызвать `check()` | Новый запрос разрешён | Unit | `test_request_is_allowed_after_window_expires` | `tests/unit/test_rate_limiter.py` |
| RATE-LIMIT-CLEANUP-001 | Старые записи удаляются лениво | Управляемые часы | Истёкший client key | Вызвать `check()` для нового клиента | Старый ключ удалён | Unit | `test_old_records_are_cleaned_lazily` | `tests/unit/test_rate_limiter.py` |
| RATE-LIMIT-INDEPENDENT-IP-001 | Разные client key независимы | In-memory limiter | `client-a`, `client-b` | Исчерпать первый лимит | Второй клиент разрешён | Unit | `test_different_clients_have_independent_limits` | `tests/unit/test_rate_limiter.py` |
| RATE-LIMIT-UNKNOWN-001 | Unknown client key обрабатывается предсказуемо | In-memory limiter | `ip_sha256:unknown` | Два запроса при лимите 1 | Первый разрешён, второй отклонён | Unit | `test_unknown_client_key_is_handled_predictably` | `tests/unit/test_rate_limiter.py` |
| RATE-LIMIT-RETRY-AFTER-001 | Retry-After рассчитывается корректно | Управляемые часы | Запросы на 0 и 10 секунде | Превысить лимит на 15 секунде | `retry_after=45` | Unit | `test_retry_after_is_calculated_from_oldest_active_hit` | `tests/unit/test_rate_limiter.py` |
| RATE-LIMIT-CLEANUP-002 | Очистка не ломает активные записи | Управляемые часы | Старый и активный timestamps | Выполнить очистку | Активный timestamp остаётся | Unit | `test_cleanup_keeps_active_records` | `tests/unit/test_rate_limiter.py` |
| RATE-LIMIT-CONCURRENCY-001 | Параллельная безопасность | ThreadPoolExecutor | 20 параллельных проверок | Вызвать `check()` | Разрешено ровно 5 при лимите 5 | Unit | `test_parallel_checks_do_not_exceed_limit` | `tests/unit/test_rate_limiter.py` |
| RATE-LIMIT-CONFIG-001 | Некорректная конфигурация отклоняется | Нет | Ноль/отрицательные значения | Создать limiter | `ValueError` | Unit | `test_invalid_limiter_configuration_is_rejected` | `tests/unit/test_rate_limiter.py` |
| RATE-LIMIT-IP-DIRECT-001 | IP берётся из `request.client.host` | Нет trusted header | IPv4 host | Вызвать `resolve_client_ip()` | Возвращён host | Unit | `test_client_ip_uses_request_client_host` | `tests/unit/test_client_ip.py` |
| RATE-LIMIT-IP-PROXY-001 | Trusted `X-Forwarded-For` используется | `TRUST_PROXY_HEADERS=true` | Proxy header | Вызвать `resolve_client_ip()` | Возвращён header IP | Unit | `test_client_ip_uses_x_forwarded_for_when_trusted` | `tests/unit/test_client_ip.py` |
| RATE-LIMIT-IP-PROXY-002 | Первый валидный адрес из цепочки | `TRUST_PROXY_HEADERS=true` | `bad, ip, proxy` | Вызвать `resolve_client_ip()` | Возвращён первый валидный IP | Unit | `test_client_ip_uses_first_valid_forwarded_address` | `tests/unit/test_client_ip.py` |
| RATE-LIMIT-IP-UNTRUSTED-001 | Header игнорируется без доверия | `TRUST_PROXY_HEADERS=false` | Header и direct host | Вызвать `resolve_client_ip()` | Возвращён direct host | Unit | `test_client_ip_ignores_forwarded_header_when_untrusted` | `tests/unit/test_client_ip.py` |
| RATE-LIMIT-IP-FALLBACK-001 | Некорректный header даёт fallback host | Некорректный header | `not-an-ip` | Вызвать `resolve_client_ip()` | Возвращён direct host | Unit | `test_invalid_forwarded_header_falls_back_to_request_client` | `tests/unit/test_client_ip.py` |
| RATE-LIMIT-IP-FALLBACK-002 | Отсутствующий client даёт unknown | Нет client | Нет host | Вызвать `resolve_client_ip()` | Возвращён `unknown-client` | Unit | `test_missing_client_host_returns_unknown` | `tests/unit/test_client_ip.py` |
| RATE-LIMIT-IP-V4-001 | IPv4 поддерживается | Нет | IPv4 | Вызвать `resolve_client_ip()` | IPv4 принят | Unit | `test_ipv4_address_is_supported` | `tests/unit/test_client_ip.py` |
| RATE-LIMIT-IP-V6-001 | IPv6 поддерживается | Нет | IPv6 | Вызвать `resolve_client_ip()` | IPv6 принят | Unit | `test_ipv6_address_is_supported` | `tests/unit/test_client_ip.py` |
| RATE-LIMIT-CLIENT-KEY-001 | Client key стабилен и маскирует IP | Нет | IP address | Вызвать `build_client_key()` | Hash стабилен, полный IP отсутствует | Unit | `test_client_key_is_stable_and_masks_ip` | `tests/unit/test_client_ip.py` |
| RATE-LIMIT-API-ALLOWED-001 | Запросы в пределах лимита создают обращения | API, временная SQLite, fake services | 2 валидных POST | POST `/api/contact` | HTTP 201, 2 записи, pipeline вызван 2 раза | Integration | `test_contact_requests_within_limit_are_created` | `tests/integration/test_contact_rate_limit.py` |
| RATE-LIMIT-API-EXCEEDED-001 | Превышение лимита даёт 429 | API, лимит 2 | 3 валидных POST | POST `/api/contact` | HTTP 429, безопасный body, `Retry-After` | Integration | `test_contact_request_over_limit_returns_429_without_pipeline` | `tests/integration/test_contact_rate_limit.py` |
| RATE-LIMIT-NO-PIPELINE-001 | 429 не вызывает pipeline | API, fake services | Запрос сверх лимита | POST `/api/contact` | Нет новой записи, AI/email не вызваны | Integration | `test_contact_request_over_limit_returns_429_without_pipeline` | `tests/integration/test_contact_rate_limit.py` |
| RATE-LIMIT-LOGGING-001 | Превышение лимита логируется без полного IP | API, caplog | Запрос сверх лимита | Проверить логи | Есть `client_key=ip_sha256`, полного IP нет | Integration | `test_contact_request_over_limit_returns_429_without_pipeline` | `tests/integration/test_contact_rate_limit.py` |
| RATE-LIMIT-API-INDEPENDENT-IP-001 | Разные IP независимы в API | Trusted proxy headers | Два IP | POST `/api/contact` | Заблокированный IP не блокирует второй | Integration | `test_different_ips_have_independent_contact_limits` | `tests/integration/test_contact_rate_limit.py` |
| RATE-LIMIT-API-WINDOW-001 | Истечение окна разрешает новый API-запрос | Управляемые часы | Перемотка на 61 секунду | POST `/api/contact` | Новый запрос создаёт запись | Integration | `test_contact_request_is_allowed_after_rate_limit_window` | `tests/integration/test_contact_rate_limit.py` |
| RATE-LIMIT-API-INVALID-001 | Невалидный запрос учитывается в лимите | API, лимит 1 | Невалидный POST, затем валидный | POST `/api/contact` | Первый 422, второй 429, pipeline не вызван | Integration | `test_invalid_contact_request_counts_toward_rate_limit` | `tests/integration/test_contact_rate_limit.py` |
| HONEYPOT-API-001 | Honeypot не создаёт запись и логируется | API, fake services | `website=bot` | POST `/api/contact` | HTTP 422, записи нет, pipeline не вызван, событие в логах | Integration | `test_honeypot_request_does_not_create_contact_and_is_logged` | `tests/integration/test_contact_rate_limit.py` |

## Автоматические сценарии этапа 8

Все проверки этапа 8 выполняются без ProxyAPI и Resend. Health проверяет только локальную БД и готовность конфигурации, metrics возвращает только обезличенные агрегаты.

| ID | Описание | Предусловия | Входные данные | Шаги | Ожидаемый результат | Тип теста | Тестовая функция | Файл теста |
| -- | -------- | ----------- | -------------- | ---- | ------------------- | -------- | ---------------- | ---------- |
| METRICS-SCHEMA-001 | Валидная схема метрик принимается | Нет | Валидный payload | Создать `ContactMetricsResponse` | Схема создана | Unit | `test_valid_metrics_response_is_accepted` | `tests/unit/test_metrics_schema.py` |
| METRICS-SCHEMA-002 | Отрицательные значения отклоняются | Нет | Negative counts | Создать schema | `ValidationError` | Unit | `test_negative_metric_values_are_rejected` | `tests/unit/test_metrics_schema.py` |
| METRICS-SCHEMA-003 | `generated_at` timezone-aware | Нет | Naive datetime | Создать schema | `ValidationError` | Unit | `test_generated_at_must_be_timezone_aware` | `tests/unit/test_metrics_schema.py` |
| METRICS-SCHEMA-004 | `request_id` обязателен | Нет | Payload без request_id | Создать schema | `ValidationError` | Unit | `test_request_id_is_required` | `tests/unit/test_metrics_schema.py` |
| METRICS-SCHEMA-005 | Пустые метрики имеют стабильную структуру | Пустой `ContactMetrics` | Нет агрегатов | `build_metrics_response()` | Все enum-ключи есть с нулями | Unit | `test_empty_metrics_have_stable_structure` | `tests/unit/test_metrics_schema.py` |
| METRICS-SCHEMA-006 | Лишние персональные поля запрещены | Нет | `email` в response | Создать schema | `ValidationError` | Unit | `test_extra_personal_fields_are_forbidden` | `tests/unit/test_metrics_schema.py` |
| METRICS-SCHEMA-007 | Legacy user email block отклоняется | Нет | `emails.owner/user` | Создать schema | `ValidationError` | Unit | `test_email_metrics_rejects_legacy_user_block` | `tests/unit/test_metrics_schema.py` |
| METRICS-OWNER-EMAIL-ONLY-001 | Metrics содержит только статусы owner email | Временная SQLite | 3 обращения | GET `/api/metrics` | `emails` плоский, без `user` | Integration | `test_metrics_populated_database_returns_exact_aggregates` | `tests/integration/test_metrics_api.py` |
| HEALTH-EXTENDED-001 | Health ok при доступной БД и configured integrations | Временная SQLite | Настроенные env | GET `/api/health` и health function | `status=ok`, latency >= 0 | Unit/Integration | `test_health_is_ok_when_database_and_integrations_are_configured`, `test_health_check_returns_ok_when_database_is_available` | `tests/unit/test_health_service.py`, `tests/integration/test_health.py` |
| HEALTH-DEGRADED-AI-001 | Health degraded при отключённом AI | Временная SQLite | `AI_LIVE_REQUESTS_ENABLED=false` | GET `/api/health` | HTTP 200, `ai=disabled`, `status=degraded` | Unit/Integration | `test_health_is_degraded_when_ai_is_disabled`, `test_health_check_returns_degraded_when_ai_is_disabled` | `tests/unit/test_health_service.py`, `tests/integration/test_health.py` |
| HEALTH-DEGRADED-EMAIL-001 | Health degraded при ненастроенном email | Временная SQLite | Нет Resend key | GET `/api/health` | HTTP 200, `email=not_configured` | Unit/Integration | `test_health_is_degraded_when_email_is_not_configured`, `test_health_check_returns_degraded_when_email_is_not_configured` | `tests/unit/test_health_service.py`, `tests/integration/test_health.py` |
| HEALTH-DEGRADED-BOTH-001 | Health degraded при отключённых integrations | Временная SQLite | AI/email disabled | Вызвать health logic | `status=degraded` | Unit | `test_health_is_degraded_when_integrations_are_disabled` | `tests/unit/test_health_service.py` |
| HEALTH-DATABASE-UNAVAILABLE-001 | Health unavailable при недоступной БД | Некорректный SQLite path | GET `/api/health` | HTTP 503, безопасный body | Unit/Integration | `test_database_health_raises_when_database_is_unavailable`, `test_health_check_returns_safe_error_when_database_is_unavailable` | `tests/unit/test_health_service.py`, `tests/integration/test_health.py` |
| HEALTH-NO-EXTERNAL-CALLS-001 | Health не вызывает ProxyAPI/Resend | Provider clients заменены ошибками | GET `/api/health` | HTTP 200 без внешних вызовов | Unit/Integration | `test_health_does_not_create_ai_or_resend_clients`, `test_health_check_does_not_expose_secrets_or_call_external_services` | `tests/unit/test_health_service.py`, `tests/integration/test_health.py` |
| HEALTH-SECRETS-001 | Health не раскрывает секреты | Тестовые ключи | GET `/api/health` | Ключей нет в response/logs | Unit/Integration | `test_health_does_not_expose_secrets`, `test_health_check_does_not_expose_secrets_or_call_external_services` | `tests/unit/test_health_service.py`, `tests/integration/test_health.py` |
| HEALTH-REQUEST-ID-001 | Request ID совпадает в health body/header | `X-Request-ID` | GET `/api/health` | Body и header содержат один ID | Integration | `test_health_check_returns_ok_when_database_is_available` | `tests/integration/test_health.py` |
| HEALTH-OPENAPI-001 | Health schema зарегистрирована в OpenAPI | API app | Нет | GET `/openapi.json` | 200/503 и `HealthResponse` есть | Integration | `test_health_openapi_schema_contains_extended_contract` | `tests/integration/test_health.py` |
| METRICS-EMPTY-001 | Пустая база возвращает нулевые метрики | Временная SQLite | Нет записей | GET `/api/metrics` | HTTP 200, все значения 0 | Integration | `test_metrics_empty_database_returns_zero_values` | `tests/integration/test_metrics_api.py` |
| METRICS-AGGREGATION-001 | Заполненная база возвращает точные агрегаты | Временная SQLite | 3 записи | GET `/api/metrics` | Точные processing/AI/email counts | Integration | `test_metrics_populated_database_returns_exact_aggregates` | `tests/integration/test_metrics_api.py` |
| METRICS-CATEGORIES-001 | Категории агрегируются с unknown | Временная SQLite | Known и legacy category | GET `/api/metrics` | Known counts и `unknown=1` | Integration | `test_metrics_populated_database_returns_exact_aggregates` | `tests/integration/test_metrics_api.py` |
| METRICS-NO-PII-001 | Metrics не содержит персональные данные | Временная SQLite с PII | Записи с именами/email/comment | GET `/api/metrics` | PII keys/values отсутствуют | Integration | `test_metrics_response_does_not_contain_personal_data` | `tests/integration/test_metrics_api.py` |
| METRICS-DATABASE-FAILED-001 | Metrics возвращает безопасный 503 при ошибке БД | Broken repository | Нет | GET `/api/metrics` | HTTP 503 без SQL/traceback | Integration | `test_metrics_database_error_returns_safe_503` | `tests/integration/test_metrics_api.py` |
| METRICS-NO-RATE-LIMIT-001 | Metrics и health не ограничиваются contact limiter | Contact limiter limit=1 | Несколько GET | GET `/api/metrics`, `/api/health` | Нет HTTP 429 | Integration | `test_metrics_and_health_are_not_contact_rate_limited` | `tests/integration/test_metrics_api.py` |
| METRICS-OPENAPI-001 | Metrics endpoint зарегистрирован в OpenAPI | API app | Нет | GET `/openapi.json` | 200/503 и schema есть | Integration | `test_metrics_openapi_contains_endpoint_and_responses` | `tests/integration/test_metrics_api.py` |

## Автоматические сценарии этапа 9

Проверки этапа 9 выполняются без browser automation, npm, ProxyAPI, Resend и production-БД. UI-контракт проверяется через FastAPI `TestClient`, HTML/static строковые проверки и один fake API-сценарий совместимости с `POST /api/contact`.

| ID | Описание | Предусловия | Входные данные | Шаги | Ожидаемый результат | Тип теста | Тестовая функция | Файл теста |
| -- | -------- | ----------- | -------------- | ---- | ------------------- | -------- | ---------------- | ---------- |
| LANDING-PAGE-001 | Главная страница отдаёт HTML и request ID | TestClient | GET `/` | Запросить страницу | HTTP 200, `text/html`, форма, ссылки и `X-Request-ID` | Integration | `test_landing_page_returns_html_with_request_id` | `tests/integration/test_landing_page.py` |
| LANDING-FORM-FIELDS-001 | Форма содержит поля обращения | TestClient | GET `/` | Проверить HTML | Есть `name`, `phone`, `email`, `comment` | Integration | `test_landing_page_contains_contact_fields_and_honeypot` | `tests/integration/test_landing_page.py` |
| LANDING-HONEYPOT-001 | Honeypot присутствует и скрыт визуально | TestClient | GET `/` | Проверить `website`, CSS-класс и `tabindex=-1` | Honeypot есть и не попадает в tab order | Integration | `test_landing_page_contains_contact_fields_and_honeypot` | `tests/integration/test_landing_page.py` |
| LANDING-ACCESSIBILITY-001 | Форма содержит базовую доступную разметку | TestClient | GET `/` | Проверить labels, constraints, submit и `aria-live` | Разметка доступна для ручной проверки | Integration | `test_landing_page_form_has_accessible_markup` | `tests/integration/test_landing_page.py` |
| LANDING-NO-SECRETS-001 | HTML/CSS/JS не раскрывают секреты | TestClient | HTML/static | Проверить секретные маркеры | Ключи и `.env` не отображаются | Integration | `test_landing_assets_do_not_expose_secrets` | `tests/integration/test_landing_page.py` |
| LANDING-STATIC-CSS-001 | CSS доступен через StaticFiles | TestClient | GET `/static/css/main.css` | Проверить статус и Content-Type | HTTP 200, `text/css` | Integration | `test_landing_static_css_is_available` | `tests/integration/test_landing_page.py` |
| LANDING-STATIC-JS-001 | JS доступен и использует `/api/contact` | TestClient | GET `/static/js/contact-form.js` | Проверить статус, Content-Type, endpoint и POST | HTTP 200, JavaScript содержит контракт | Integration | `test_landing_static_js_is_available_and_targets_contact_api` | `tests/integration/test_landing_page.py` |
| LANDING-FRONTEND-CONTRACT-001 | JS безопасно обрабатывает 422/429/500/network/non-JSON | TestClient | JS-файл | Проверить ключевые ветки обработки | Есть безопасные сообщения, JSON parsing и `textContent` | Integration | `test_landing_frontend_contract_handles_errors_safely` | `tests/integration/test_landing_page.py` |
| LANDING-SECURITY-001 | Нет внешних scripts и inline handlers | TestClient | GET `/` | Проверить HTML | Нет внешних scripts, inline handlers и iframe | Integration | `test_landing_security_has_no_external_scripts_or_inline_handlers` | `tests/integration/test_landing_page.py` |
| LANDING-API-COMPATIBILITY-001 | Frontend-сценарий совместим с `POST /api/contact` | Временная SQLite, fake AI/email | Валидный JSON | GET `/`, затем POST `/api/contact` | API возвращает HTTP 201 и безопасный body | Integration | `test_landing_api_compatibility_accepts_contact_payload` | `tests/integration/test_landing_page.py` |
| UI-NO-EMAIL-CONFIRMATION-001 | Frontend не обещает письмо пользователю | TestClient | HTML и JS | Проверить тексты | Нет формулировок `проверьте почту`, `вам отправлено письмо`, `ответ направлен на email` | Integration | `test_landing_frontend_does_not_claim_user_email_confirmation` | `tests/integration/test_landing_page.py` |

## Ручные сценарии

- Выполнить `alembic upgrade head` из корня проекта.
- Выполнить `python -m app.cli check-foundation`.
- При необходимости запустить `uvicorn app.main:app --reload` и открыть `/docs`.
- Выполнить `GET /api/health` через браузер или HTTP-клиент.

### UI-LANDING-001

- Открыть `/`.
- Проверить отображение desktop.
- Проверить отображение узкого окна.
- Ожидаемый результат: страница читаема, без горизонтального скролла, ссылки `/docs`, `/api/health`, `/api/metrics` доступны.

### UI-FORM-SUCCESS-001

- Заполнить валидные тестовые данные.
- Отправить форму.
- Проверить loading, success `Обращение принято` и очистку формы.

### UI-FORM-VALIDATION-001

- Ввести имя с цифрами, некорректный email и короткий комментарий.
- Отправить форму.
- Ожидаемый результат: общий текст `Проверьте заполненные данные.` и ошибки рядом с полями.

### UI-FORM-RATE-LIMIT-001

- Перед проверкой установить `AI_LIVE_REQUESTS_ENABLED=false` и `EMAIL_LIVE_REQUESTS_ENABLED=false`.
- Выполнить отправки до превышения лимита.
- Ожидаемый результат: HTTP 429 и сообщение `Слишком много обращений. Попробуйте повторить позже.`

### UI-FORM-NETWORK-001

- Остановить сервер.
- Отправить форму с уже открытой страницы.
- Ожидаемый результат: сообщение `Не удалось связаться с сервером. Проверьте соединение и повторите попытку.`

### UI-FORM-SERVER-001

- Имитировать безопасный HTTP 500.
- Ожидаемый результат: общее сообщение об ошибке и request ID, если API вернул его.

### UI-FORM-KEYBOARD-001

- Пройти форму клавиатурой.
- Проверить видимый focus.
- Отправить форму Enter или кнопкой.

### UI-FORM-XSS-001

- Вставить HTML/JS в комментарий.
- Убедиться, что страница не выполняет скрипт и не использует `innerHTML` для server data.

### UI-HONEYPOT-001

- Через DevTools заполнить скрытое поле `website`.
- Отправить форму.
- Ожидаемый результат: обращение не создаётся, пользователь не видит специального сообщения про honeypot.

## Таблица соответствия

| ID | Сценарий | Тип | Автоматизирован | Файл теста | Пройдено |
| -- | -------- | --- | --------------- | ---------- | -------- |
| HEALTH-001 | Успешный health check | Integration | Да | `tests/integration/test_health.py` | [x] |
| HEALTH-002 | Health check при недоступной БД | Integration | Да | `tests/integration/test_health.py` | [x] |
| CONFIG-001 | Настройки загружаются из окружения | Unit | Да | `tests/unit/test_config.py` | [x] |
| LOGGING-001 | HTTP-запрос получает request ID | Integration | Да | `tests/integration/test_logging.py` | [x] |
| LOGGING-002 | Завершение запроса фиксируется в логах | Integration | Да | `tests/integration/test_logging.py` | [x] |
| ERROR-001 | Необработанная ошибка возвращает безопасный ответ | Integration | Да | `tests/integration/test_errors.py` | [x] |
| NORMALIZATION-001 | Однострочный текст очищается и схлопывает пробелы | Unit | Да | `tests/unit/test_normalizers.py` | [x] |
| NORMALIZATION-002 | Переводы строк в однострочном поле становятся пробелом | Unit | Да | `tests/unit/test_normalizers.py` | [x] |
| NORMALIZATION-EMAIL-001 | Email очищается и приводится к нижнему регистру | Unit | Да | `tests/unit/test_normalizers.py` | [x] |
| NORMALIZATION-PHONE-001 | Российский телефон с `8` приводится к `+7` | Unit | Да | `tests/unit/test_normalizers.py` | [x] |
| NORMALIZATION-PHONE-002 | Российский телефон с `+7` очищается | Unit | Да | `tests/unit/test_normalizers.py` | [x] |
| NORMALIZATION-PHONE-003 | Международный телефон сохраняет код страны | Unit | Да | `tests/unit/test_normalizers.py` | [x] |
| NORMALIZATION-PHONE-004 | Телефон очищается от пробелов по краям | Unit | Да | `tests/unit/test_normalizers.py` | [x] |
| NORMALIZATION-COMMENT-001 | Комментарий очищается только по краям | Unit | Да | `tests/unit/test_normalizers.py` | [x] |
| VALIDATION-PHONE-001 | Нормализатор отклоняет буквы в телефоне | Unit | Да | `tests/unit/test_normalizers.py` | [x] |
| VALIDATION-PHONE-002 | Нормализатор отклоняет посторонний спецсимвол | Unit | Да | `tests/unit/test_normalizers.py` | [x] |
| VALIDATION-NAME-001 | Обычное русское имя допустимо | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-002 | Имя и фамилия допустимы | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-003 | Повторяющиеся пробелы в имени схлопываются | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-004 | Дефис в имени допустим | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-005 | Апостроф в имени допустим | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-006 | Латинское имя допустимо | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-007 | Несколько частей имени допустимы | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-008 | Цифра в имени запрещена | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-009 | Подчёркивание в имени запрещено | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-010 | `@` в имени запрещён | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-011 | Имя только из пробелов запрещено | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-012 | Слишком короткое имя запрещено | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-013 | Слишком длинное имя запрещено | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-014 | Разделители подряд запрещены | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-015 | Разделитель в начале запрещён | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-016 | Разделитель в конце запрещён | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-NAME-017 | Разделитель рядом с пробелом запрещён | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-PHONE-003 | Российский телефон с `8` принимается | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-PHONE-004 | Российский телефон с `+7` принимается | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-PHONE-005 | Телефон со скобками и дефисами принимается | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-PHONE-006 | Международный телефон принимается | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-PHONE-007 | Пробелы по краям телефона удаляются | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-PHONE-008 | Буквы в телефоне запрещены | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-PHONE-009 | Спецсимволы в телефоне запрещены | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-PHONE-010 | Слишком короткий телефон запрещён | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-PHONE-011 | Слишком длинный телефон запрещён | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-PHONE-012 | Пустой телефон запрещён | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-EMAIL-001 | Корректный email допустим | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-EMAIL-002 | Пробелы по краям email удаляются | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-EMAIL-003 | Регистр email приводится к нижнему | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-EMAIL-004 | Внутренний пробел email запрещён | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-EMAIL-005 | Некорректный формат email запрещён | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-EMAIL-006 | Пустой email запрещён | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-COMMENT-001 | Корректный комментарий допустим | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-COMMENT-002 | Пробелы по краям комментария удаляются | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-COMMENT-003 | Внутренние повторяющиеся пробелы сохраняются | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-COMMENT-004 | Переносы строк сохраняются | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-COMMENT-005 | Абзацы сохраняются | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-COMMENT-006 | Комментарий только из пробелов запрещён | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-COMMENT-007 | Комментарий только из переносов запрещён | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-COMMENT-008 | Слишком короткий комментарий запрещён | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-COMMENT-009 | Слишком длинный комментарий запрещён | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-CONTACT-001 | Полностью валидное обращение создаёт схему | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| NORMALIZATION-CONTACT-001 | Все поля обращения возвращаются нормализованными | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-CONTACT-002 | Ошибка одного поля содержит понятную информацию | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| NORMALIZATION-COMMENT-002 | Внутренние пробелы комментария не изменяются | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| NORMALIZATION-NAME-001 | Лишние пробелы в имени не попадают в итоговые данные | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| VALIDATION-HONEYPOT-001 | Заполненный honeypot отклоняет обращение | Unit | Да | `tests/unit/test_contact_schema.py` | [x] |
| REPOSITORY-CREATE-001 | Валидное обращение создаётся и получает ID | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-CREATE-002 | При создании выставляются начальные статусы | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| DATABASE-MODEL-001 | При создании устанавливаются UTC-метки | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| DATABASE-MODEL-003 | `updated_at` меняется при обновлении | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-GET-001 | Существующее обращение возвращается по ID | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-GET-002 | Несуществующее обращение возвращает `None` | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-AI-UPDATE-001 | AI-поля сохраняются | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-AI-UPDATE-002 | AI error сохраняется | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-AI-UPDATE-003 | AI-обновление не меняет исходные данные | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-AI-UPDATE-004 | AI-обновление отсутствующего ID отклоняется | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-EMAIL-UPDATE-001 | Статус письма владельцу обновляется отдельно | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| EMAIL-OWNER-ONLY-001 | Email-статусы ограничены письмом владельцу | Unit | Да | `tests/unit/test_contact_repository.py`, `tests/unit/test_email_templates.py` | [x] |
| REPOSITORY-STATUS-001 | Общий статус обработки обновляется отдельно | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-METRICS-001 | Пустая база возвращает нулевые метрики | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-METRICS-002 | Несколько записей корректно агрегируются | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-METRICS-003 | Метрики не содержат персональные данные | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-ROLLBACK-001 | Ошибка сохранения выполняет rollback | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| DATABASE-MIGRATION-001 | Alembic upgrade создаёт таблицу обращений | Integration | Да | `tests/integration/test_database.py` | [x] |
| DATABASE-MODEL-002 | Модель совместима с актуальной миграцией | Integration | Да | `tests/integration/test_database.py` | [x] |
| DATABASE-MIGRATION-002 | Alembic downgrade возвращает legacy user email поля | Integration | Да | `tests/integration/test_database.py` | [x] |
| DATABASE-REMOVE-USER-EMAIL-FIELDS-001 | Актуальный upgrade удаляет legacy user email поля | Integration | Да | `tests/integration/test_database.py` | [x] |
| AI-SCHEMA-001 | Валидный AI-результат принимается | Unit | Да | `tests/unit/test_ai_schemas.py` | [x] |
| AI-SCHEMA-002 | Неизвестные enum-значения отклоняются | Unit | Да | `tests/unit/test_ai_schemas.py` | [x] |
| AI-SCHEMA-003 | Слишком длинный summary отклоняется | Unit | Да | `tests/unit/test_ai_schemas.py` | [x] |
| AI-SCHEMA-004 | Пустой suggested reply отклоняется | Unit | Да | `tests/unit/test_ai_schemas.py` | [x] |
| AI-SCHEMA-005 | Fallback analysis соответствует схеме | Unit | Да | `tests/unit/test_ai_schemas.py` | [x] |
| AI-SCHEMA-006 | Fallback service result содержит статус | Unit | Да | `tests/unit/test_ai_schemas.py` | [x] |
| AI-SUCCESS-001 | Валидный structured output возвращает success | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-SUCCESS-002 | Системный промпт и комментарий передаются отдельно | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-SUCCESS-003 | Project request для оценки передаётся отдельно и не меняет structured output | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-LOGGING-001 | Полный комментарий не попадает в логи | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FALLBACK-NO-KEY-001 | Fallback при отсутствии API-ключа | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FALLBACK-DISABLED-001 | Fallback при отключённых live-вызовах | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FALLBACK-TIMEOUT-001 | Fallback при timeout OpenAI | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FALLBACK-CONNECTION-001 | Fallback при ошибке соединения | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FALLBACK-AUTH-001 | Fallback при ошибке авторизации | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FALLBACK-PERMISSION-001 | Fallback при запрете доступа OpenAI/ProxyAPI | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FALLBACK-PERMISSION-002 | Детали запрета доступа безопасно сохраняются | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FALLBACK-RATE-LIMIT-001 | Fallback при rate limit | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FALLBACK-API-001 | Fallback при общей API-ошибке | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FALLBACK-INVALID-RESPONSE-001 | Fallback при невалидном structured output | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FALLBACK-EMPTY-001 | Fallback при пустом ответе | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FALLBACK-UNEXPECTED-001 | Fallback при неожиданной ошибке | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-PROMPT-SUGGESTED-REPLY-001 | System prompt требует содержательный suggested reply от первого лица | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-PROMPT-PROJECT-REQUEST-001 | System prompt задаёт поведение для project_request | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-PROMPT-INJECTION-001 | Prompt injection остаётся пользовательскими данными | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FAKE-001 | Fake success возвращает результат | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FAKE-002 | Fake fallback возвращает fallback | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FAKE-003 | Fake error имитирует исключение | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FAKE-004 | Fake service не создаёт OpenAI-клиент | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FAKE-005 | Fake project_request содержит персональный полезный suggested reply | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-PROXY-001 | OpenAI SDK получает custom base_url | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-LIVE-001 | Один контролируемый live-запрос через ProxyAPI | Manual | Нет | CLI manual | [x] |
| EMAIL-SCHEMA-001 | Валидное email-сообщение принимается | Unit | Да | `tests/unit/test_email_schemas.py` | [x] |
| EMAIL-SCHEMA-002 | Невалидные поля письма отклоняются | Unit | Да | `tests/unit/test_email_schemas.py` | [x] |
| EMAIL-SCHEMA-003 | Валидный результат отправки принимается | Unit | Да | `tests/unit/test_email_schemas.py` | [x] |
| EMAIL-SCHEMA-004 | Неизвестный email-статус отклоняется | Unit | Да | `tests/unit/test_email_schemas.py` | [x] |
| EMAIL-RENDER-OWNER-001 | Письмо владельцу рендерится | Unit | Да | `tests/unit/test_email_templates.py` | [x] |
| EMAIL-NO-USER-AUTOREPLY-001 | Автоматическое письмо пользователю не предусмотрено | Unit | Да | `tests/unit/test_email_templates.py`, `tests/unit/test_email_service.py` | [x] |
| EMAIL-RENDER-OPTIONAL-001 | Optional-поля не выводят `None` | Unit | Да | `tests/unit/test_email_templates.py` | [x] |
| EMAIL-HTML-ESCAPE-001 | HTML комментария экранируется | Unit | Да | `tests/unit/test_email_templates.py` | [x] |
| EMAIL-TEXT-001 | Переносы строк комментария сохраняются | Unit | Да | `tests/unit/test_email_templates.py` | [x] |
| EMAIL-HTML-ESCAPE-002 | Suggested reply экранируется | Unit | Да | `tests/unit/test_email_templates.py` | [x] |
| EMAIL-RENDER-FALLBACK-001 | AI fallback отображается в письме владельцу | Unit | Да | `tests/unit/test_email_templates.py` | [x] |
| EMAIL-SEND-PAYLOAD-001 | Payload Resend формируется корректно | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-SEND-OWNER-001 | Письмо владельцу отправляется на `OWNER_EMAIL` | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-OWNER-REPLY-TO-001 | Reply-To письма владельцу равен email пользователя | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-SEND-RESULT-001 | Успешный ответ сохраняет provider message id | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-SKIPPED-DISABLED-001 | Live отключён возвращает skipped | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-FAILED-CONFIG-001 | Отсутствующие настройки возвращают failed | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-FAILED-CONFIG-002 | Sender с именем в `EMAIL_FROM_ADDRESS` отклоняется | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-FAILED-PROVIDER-001 | Ошибки Resend возвращают failed | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-FAILED-INVALID-RESPONSE-001 | Ответ без id считается ошибкой | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-LOGGING-001 | Тело письма и PII не попадают в логи | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-FAKE-001 | Fake-сервис поддерживает success/failed/skipped | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-FAKE-002 | Fake exception имитирует ошибку | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-FAKE-003 | Fake-сервис не вызывает Resend | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-LIVE-001 | Одно контролируемое live-письмо через Resend | Manual | Нет | CLI manual | [ ] |
| PIPELINE-SUCCESS-001 | Полный pipeline успешно завершается | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
| PIPELINE-AI-FALLBACK-001 | AI fallback не останавливает pipeline | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
| PIPELINE-AI-EXCEPTION-001 | Исключение AI превращается в fallback | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
| PIPELINE-OWNER-EMAIL-FAILED-001 | Ошибка письма владельцу даёт частичный успех | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
| PIPELINE-SINGLE-EMAIL-001 | Pipeline отправляет ровно одно письмо владельцу | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
| PIPELINE-EMAILS-FAILED-001 | Ошибка письма владельцу не удаляет AI-результат | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
| PIPELINE-EMAIL-SKIPPED-001 | Skipped owner email считается частичной ошибкой | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
| PIPELINE-REPOSITORY-CREATE-FAILED-001 | Ошибка create останавливает внешние этапы | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
| PIPELINE-REPOSITORY-UPDATE-FAILED-001 | Ошибка сохранения AI критична | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
| PIPELINE-REPOSITORY-EMAIL-UPDATE-FAILED-001 | Ошибка сохранения email-статуса критична | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
| PIPELINE-STATUS-001 | External errors не дают `failed` | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
| CONTACT-API-SUCCESS-001 | POST `/api/contact` успешно создаёт обращение | Integration | Да | `tests/integration/test_contact_api.py` | [x] |
| CONTACT-API-AI-FALLBACK-001 | API возвращает 201 при AI fallback | Integration | Да | `tests/integration/test_contact_api.py` | [x] |
| CONTACT-API-EMAIL-FAILED-001 | API возвращает 201 при email failed | Integration | Да | `tests/integration/test_contact_api.py` | [x] |
| CONTACT-API-VALIDATION-001 | Невалидные данные дают 422 | Integration | Да | `tests/integration/test_contact_api.py` | [x] |
| CONTACT-API-DATABASE-FAILED-001 | Ошибка create даёт безопасный 500 | Integration | Да | `tests/integration/test_contact_api.py` | [x] |
| CONTACT-API-REQUEST-ID-001 | Request ID совпадает в header и body | Integration | Да | `tests/integration/test_contact_api.py` | [x] |
| CONTACT-API-OPENAPI-001 | Endpoint зарегистрирован в OpenAPI | Integration | Да | `tests/integration/test_contact_api.py` | [x] |
| RATE-LIMIT-UNIT-001 | Первые запросы в пределах лимита разрешены | Unit | Да | `tests/unit/test_rate_limiter.py` | [x] |
| RATE-LIMIT-UNIT-002 | Запрос сверх лимита отклоняется | Unit | Да | `tests/unit/test_rate_limiter.py` | [x] |
| RATE-LIMIT-WINDOW-001 | После окончания окна запрос снова разрешён | Unit | Да | `tests/unit/test_rate_limiter.py` | [x] |
| RATE-LIMIT-CLEANUP-001 | Старые записи удаляются лениво | Unit | Да | `tests/unit/test_rate_limiter.py` | [x] |
| RATE-LIMIT-INDEPENDENT-IP-001 | Разные client key независимы | Unit | Да | `tests/unit/test_rate_limiter.py` | [x] |
| RATE-LIMIT-UNKNOWN-001 | Unknown client key получает обычный лимит | Unit | Да | `tests/unit/test_rate_limiter.py` | [x] |
| RATE-LIMIT-RETRY-AFTER-001 | Retry-After рассчитывается корректно | Unit | Да | `tests/unit/test_rate_limiter.py` | [x] |
| RATE-LIMIT-CLEANUP-002 | Очистка не ломает активные записи | Unit | Да | `tests/unit/test_rate_limiter.py` | [x] |
| RATE-LIMIT-CONCURRENCY-001 | Параллельные проверки не превышают лимит | Unit | Да | `tests/unit/test_rate_limiter.py` | [x] |
| RATE-LIMIT-CONFIG-001 | Некорректная конфигурация limiter отклоняется | Unit | Да | `tests/unit/test_rate_limiter.py` | [x] |
| RATE-LIMIT-IP-DIRECT-001 | IP берётся из `request.client.host` | Unit | Да | `tests/unit/test_client_ip.py` | [x] |
| RATE-LIMIT-IP-PROXY-001 | Trusted `X-Forwarded-For` используется | Unit | Да | `tests/unit/test_client_ip.py` | [x] |
| RATE-LIMIT-IP-PROXY-002 | Первый валидный адрес из цепочки используется | Unit | Да | `tests/unit/test_client_ip.py` | [x] |
| RATE-LIMIT-IP-UNTRUSTED-001 | Header игнорируется без доверия proxy | Unit | Да | `tests/unit/test_client_ip.py` | [x] |
| RATE-LIMIT-IP-FALLBACK-001 | Некорректный proxy header даёт fallback host | Unit | Да | `tests/unit/test_client_ip.py` | [x] |
| RATE-LIMIT-IP-FALLBACK-002 | Отсутствующий client host даёт unknown | Unit | Да | `tests/unit/test_client_ip.py` | [x] |
| RATE-LIMIT-IP-V4-001 | IPv4 поддерживается | Unit | Да | `tests/unit/test_client_ip.py` | [x] |
| RATE-LIMIT-IP-V6-001 | IPv6 поддерживается | Unit | Да | `tests/unit/test_client_ip.py` | [x] |
| RATE-LIMIT-CLIENT-KEY-001 | Client key стабилен и маскирует IP | Unit | Да | `tests/unit/test_client_ip.py` | [x] |
| RATE-LIMIT-API-ALLOWED-001 | Запросы в пределах лимита создают обращения | Integration | Да | `tests/integration/test_contact_rate_limit.py` | [x] |
| RATE-LIMIT-API-EXCEEDED-001 | Превышение лимита даёт 429 | Integration | Да | `tests/integration/test_contact_rate_limit.py` | [x] |
| RATE-LIMIT-NO-PIPELINE-001 | 429 не вызывает pipeline | Integration | Да | `tests/integration/test_contact_rate_limit.py` | [x] |
| RATE-LIMIT-LOGGING-001 | Превышение логируется без полного IP | Integration | Да | `tests/integration/test_contact_rate_limit.py` | [x] |
| RATE-LIMIT-API-INDEPENDENT-IP-001 | Разные IP независимы в API | Integration | Да | `tests/integration/test_contact_rate_limit.py` | [x] |
| RATE-LIMIT-API-WINDOW-001 | Истечение окна разрешает новый API-запрос | Integration | Да | `tests/integration/test_contact_rate_limit.py` | [x] |
| RATE-LIMIT-API-INVALID-001 | Невалидный запрос учитывается в лимите | Integration | Да | `tests/integration/test_contact_rate_limit.py` | [x] |
| HONEYPOT-API-001 | Honeypot не создаёт запись и логируется | Integration | Да | `tests/integration/test_contact_rate_limit.py` | [x] |
| METRICS-SCHEMA-001 | Валидная схема метрик принимается | Unit | Да | `tests/unit/test_metrics_schema.py` | [x] |
| METRICS-SCHEMA-002 | Отрицательные значения метрик отклоняются | Unit | Да | `tests/unit/test_metrics_schema.py` | [x] |
| METRICS-SCHEMA-003 | `generated_at` требует timezone | Unit | Да | `tests/unit/test_metrics_schema.py` | [x] |
| METRICS-SCHEMA-004 | `request_id` обязателен | Unit | Да | `tests/unit/test_metrics_schema.py` | [x] |
| METRICS-SCHEMA-005 | Пустые метрики имеют стабильную структуру | Unit | Да | `tests/unit/test_metrics_schema.py` | [x] |
| METRICS-SCHEMA-006 | Лишние персональные поля запрещены | Unit | Да | `tests/unit/test_metrics_schema.py` | [x] |
| METRICS-SCHEMA-007 | Legacy user email block отклоняется | Unit | Да | `tests/unit/test_metrics_schema.py` | [x] |
| METRICS-OWNER-EMAIL-ONLY-001 | Metrics содержит только статусы owner email | Integration | Да | `tests/integration/test_metrics_api.py` | [x] |
| HEALTH-EXTENDED-001 | Health ok при доступной БД и configured integrations | Unit/Integration | Да | `tests/unit/test_health_service.py`, `tests/integration/test_health.py` | [x] |
| HEALTH-DEGRADED-AI-001 | Health degraded при отключённом AI | Unit/Integration | Да | `tests/unit/test_health_service.py`, `tests/integration/test_health.py` | [x] |
| HEALTH-DEGRADED-EMAIL-001 | Health degraded при ненастроенном email | Unit/Integration | Да | `tests/unit/test_health_service.py`, `tests/integration/test_health.py` | [x] |
| HEALTH-DEGRADED-BOTH-001 | Health degraded при отключённых integrations | Unit | Да | `tests/unit/test_health_service.py` | [x] |
| HEALTH-DATABASE-UNAVAILABLE-001 | Health unavailable при недоступной БД | Unit/Integration | Да | `tests/unit/test_health_service.py`, `tests/integration/test_health.py` | [x] |
| HEALTH-NO-EXTERNAL-CALLS-001 | Health не вызывает ProxyAPI/Resend | Unit/Integration | Да | `tests/unit/test_health_service.py`, `tests/integration/test_health.py` | [x] |
| HEALTH-SECRETS-001 | Health не раскрывает секреты | Unit/Integration | Да | `tests/unit/test_health_service.py`, `tests/integration/test_health.py` | [x] |
| HEALTH-REQUEST-ID-001 | Request ID совпадает в health body/header | Integration | Да | `tests/integration/test_health.py` | [x] |
| HEALTH-OPENAPI-001 | Health schema зарегистрирована в OpenAPI | Integration | Да | `tests/integration/test_health.py` | [x] |
| METRICS-EMPTY-001 | Пустая база возвращает нулевые метрики | Integration | Да | `tests/integration/test_metrics_api.py` | [x] |
| METRICS-AGGREGATION-001 | Заполненная база возвращает точные агрегаты | Integration | Да | `tests/integration/test_metrics_api.py` | [x] |
| METRICS-CATEGORIES-001 | Категории агрегируются с unknown | Integration | Да | `tests/integration/test_metrics_api.py` | [x] |
| METRICS-NO-PII-001 | Metrics не содержит персональные данные | Integration | Да | `tests/integration/test_metrics_api.py` | [x] |
| METRICS-DATABASE-FAILED-001 | Metrics возвращает безопасный 503 при ошибке БД | Integration | Да | `tests/integration/test_metrics_api.py` | [x] |
| METRICS-NO-RATE-LIMIT-001 | Metrics и health не ограничиваются contact limiter | Integration | Да | `tests/integration/test_metrics_api.py` | [x] |
| METRICS-OPENAPI-001 | Metrics endpoint зарегистрирован в OpenAPI | Integration | Да | `tests/integration/test_metrics_api.py` | [x] |
| LANDING-PAGE-001 | Главная страница отдаёт HTML и request ID | Integration | Да | `tests/integration/test_landing_page.py` | [x] |
| LANDING-FORM-FIELDS-001 | Форма содержит поля обращения | Integration | Да | `tests/integration/test_landing_page.py` | [x] |
| LANDING-HONEYPOT-001 | Honeypot присутствует и скрыт визуально | Integration | Да | `tests/integration/test_landing_page.py` | [x] |
| LANDING-ACCESSIBILITY-001 | Форма содержит базовую доступную разметку | Integration | Да | `tests/integration/test_landing_page.py` | [x] |
| LANDING-NO-SECRETS-001 | HTML/CSS/JS не раскрывают секреты | Integration | Да | `tests/integration/test_landing_page.py` | [x] |
| LANDING-STATIC-CSS-001 | CSS доступен через StaticFiles | Integration | Да | `tests/integration/test_landing_page.py` | [x] |
| LANDING-STATIC-JS-001 | JS доступен и использует `/api/contact` | Integration | Да | `tests/integration/test_landing_page.py` | [x] |
| LANDING-FRONTEND-CONTRACT-001 | JS безопасно обрабатывает ошибки API и сети | Integration | Да | `tests/integration/test_landing_page.py` | [x] |
| LANDING-SECURITY-001 | Нет внешних scripts и inline handlers | Integration | Да | `tests/integration/test_landing_page.py` | [x] |
| LANDING-API-COMPATIBILITY-001 | Frontend-сценарий совместим с `POST /api/contact` | Integration | Да | `tests/integration/test_landing_page.py` | [x] |
| UI-NO-EMAIL-CONFIRMATION-001 | Frontend не обещает письмо пользователю | Integration | Да | `tests/integration/test_landing_page.py` | [x] |
| UI-LANDING-001 | Проверка desktop/mobile отображения `/` | Manual | Нет | Browser manual | [ ] |
| UI-FORM-SUCCESS-001 | Успешная отправка формы в браузере | Manual | Нет | Browser manual | [ ] |
| UI-FORM-VALIDATION-001 | Field errors при 422 в браузере | Manual | Нет | Browser manual | [ ] |
| UI-FORM-RATE-LIMIT-001 | Сообщение при HTTP 429 | Manual | Нет | Browser manual | [ ] |
| UI-FORM-NETWORK-001 | Сообщение при network error | Manual | Нет | Browser manual | [ ] |
| UI-FORM-SERVER-001 | Сообщение при HTTP 500 и request ID | Manual | Нет | Browser manual | [ ] |
| UI-FORM-KEYBOARD-001 | Клавиатурная навигация и focus | Manual | Нет | Browser manual | [ ] |
| UI-FORM-XSS-001 | HTML/JS в комментарии не исполняется | Manual | Нет | Browser manual | [ ] |
| UI-HONEYPOT-001 | Заполненный honeypot не создаёт обращение | Manual | Нет | Browser manual | [ ] |

## Финальный checklist перед сдачей проекта

- [ ] Все автоматические тесты пройдены.
- [ ] Ручной health check выполнен.
- [ ] Миграции применяются из чистого состояния.
- [ ] AI live-вызов через ProxyAPI выполнен только при явном разрешении.
- [ ] Реальное тестовое письмо отправлено только при явном разрешении.
- [ ] Секреты отсутствуют в репозитории.
- [ ] README финального этапа описывает запуск, API, деплой и ограничения.
