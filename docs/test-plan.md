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
| REPOSITORY-EMAIL-UPDATE-001 | Статус письма владельцу обновляется отдельно | Временная SQLite | `owner=sent` | Вызвать `update_owner_email_status()` | User email status не перезаписан | Unit | `test_update_owner_email_status_updates_only_owner` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-EMAIL-UPDATE-002 | Статус письма пользователю обновляется отдельно | Временная SQLite | `user=failed`, error | Вызвать `update_user_email_status()` | Owner email status не перезаписан | Unit | `test_update_user_email_status_updates_only_user` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-EMAIL-UPDATE-003 | Оба email-статуса можно обновить одной операцией | Временная SQLite | Owner/user statuses | Вызвать `update_email_statuses()` | Оба статуса сохранены | Unit | `test_update_email_statuses_can_update_both_statuses` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-STATUS-001 | Общий статус обработки обновляется отдельно | Временная SQLite | `completed` | Вызвать `update_processing_status()` | Остальные поля не изменены | Unit | `test_update_processing_status_changes_only_processing_status` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-METRICS-001 | Пустая база возвращает нулевые метрики | Пустая SQLite | Нет | Вызвать `get_metrics()` | Все агрегаты пустые/нулевые | Unit | `test_get_metrics_returns_zero_values_for_empty_database` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-METRICS-002 | Несколько записей корректно агрегируются | Временная SQLite | 2 обращения с разными статусами | Вызвать `get_metrics()` | Счётчики по статусам и категориям корректны | Unit | `test_get_metrics_aggregates_multiple_contacts` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-METRICS-003 | Метрики не содержат персональные данные | Временная SQLite | Валидное обращение | Проверить результат `get_metrics()` | Нет имени, email, телефона, комментария | Unit | `test_get_metrics_does_not_return_personal_data` | `tests/unit/test_contact_repository.py` |
| REPOSITORY-ROLLBACK-001 | Ошибка сохранения выполняет rollback | Временная SQLite | Контролируемая ошибка commit | Вызвать `create()` | Rollback выполнен, сессия пригодна дальше | Unit | `test_create_rolls_back_after_database_error` | `tests/unit/test_contact_repository.py` |
| DATABASE-MIGRATION-001 | Alembic upgrade создаёт таблицу обращений | Временная SQLite | Миграции Alembic | `upgrade head` | Таблица и ключевые поля созданы | Integration | `test_alembic_upgrade_creates_contact_requests_table` | `tests/integration/test_database.py` |
| DATABASE-MODEL-002 | Модель совместима с актуальной миграцией | Временная SQLite после миграции | Валидное обращение | Создать через repository | Запись создаётся и читается | Integration | `test_repository_works_with_migrated_database` | `tests/integration/test_database.py` |
| DATABASE-MIGRATION-002 | Alembic downgrade удаляет таблицу обращений | Временная SQLite | Миграции Alembic | `upgrade head`, `downgrade -1` | Таблица удалена | Integration | `test_alembic_downgrade_removes_contact_requests_table` | `tests/integration/test_database.py` |

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
| AI-PROMPT-INJECTION-001 | Prompt injection остаётся пользовательскими данными | Mock OpenAI client | Инъекционный комментарий | Проверить messages и prompt | Комментарий не склеен с system prompt | Unit | `test_prompt_injection_comment_is_not_concatenated_into_system_prompt` | `tests/unit/test_ai_service.py` |
| AI-FAKE-001 | Fake success возвращает результат | Нет | Тестовый комментарий | Вызвать fake service | `status=success` | Unit | `test_fake_service_returns_success` | `tests/unit/test_ai_service.py` |
| AI-FAKE-002 | Fake fallback возвращает fallback | Нет | Тестовый комментарий | Вызвать fake service | `status=fallback` | Unit | `test_fake_service_returns_fallback` | `tests/unit/test_ai_service.py` |
| AI-FAKE-003 | Fake error имитирует исключение | Нет | Тестовый комментарий | Вызвать fake service | `RuntimeError` | Unit | `test_fake_service_can_raise_error` | `tests/unit/test_ai_service.py` |
| AI-FAKE-004 | Fake service не создаёт OpenAI-клиент | OpenAI constructor заменён ошибкой | Тестовый комментарий | Вызвать fake service | Клиент не создан | Unit | `test_fake_service_does_not_create_openai_client` | `tests/unit/test_ai_service.py` |
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
| EMAIL-RENDER-USER-001 | Письмо пользователю рендерится безопасно | Тестовый контекст | Контакт, AI error | Построить user message | Нет внутренней классификации и техошибки | Unit | `test_user_confirmation_is_rendered_without_internal_classification` | `tests/unit/test_email_templates.py` |
| EMAIL-RENDER-OPTIONAL-001 | Optional-поля не выводят `None` | Контекст без optional | Нет summary/category/status | Построить owner message | Строка `None` отсутствует | Unit | `test_missing_optional_fields_do_not_render_none` | `tests/unit/test_email_templates.py` |
| EMAIL-HTML-ESCAPE-001 | HTML комментария экранируется | Тестовый контекст | `<script>alert("xss")</script>` | Построить owner message | Тег не исполняется, текст экранирован | Unit | `test_user_html_in_comment_is_escaped` | `tests/unit/test_email_templates.py` |
| EMAIL-TEXT-001 | Переносы строк сохраняются | Тестовый контекст | многострочный комментарий | Построить owner message | Text хранит переносы, HTML использует `pre-wrap` | Unit | `test_comment_line_breaks_are_preserved` | `tests/unit/test_email_templates.py` |
| EMAIL-HTML-ESCAPE-002 | Suggested reply экранируется | Тестовый контекст | `<script>` в suggested_reply | Построить user message | HTML экранирован | Unit | `test_user_suggested_reply_is_escaped` | `tests/unit/test_email_templates.py` |
| EMAIL-RENDER-FALLBACK-001 | AI fallback отображается корректно | Тестовый контекст | `ai_status=fallback` | Построить оба письма | Владелец видит fallback, пользователь получает безопасный ответ | Unit | `test_ai_fallback_is_rendered_safely` | `tests/unit/test_email_templates.py` |
| EMAIL-SEND-PAYLOAD-001 | Payload Resend формируется корректно | Mock Resend | `EmailMessage` | Вызвать `send()` | from/to/subject/html/text/reply_to корректны | Unit | `test_resend_payload_is_built_correctly` | `tests/unit/test_email_service.py` |
| EMAIL-SEND-OWNER-001 | Уведомление владельцу отправляется на `OWNER_EMAIL` | Mock Resend | Контекст обращения | Вызвать `send_owner_notification()` | Получатель owner, reply_to пользователь | Unit | `test_owner_notification_uses_owner_email_and_user_reply_to` | `tests/unit/test_email_service.py` |
| EMAIL-SEND-USER-001 | Подтверждение отправляется пользователю | Mock Resend | Контекст обращения | Вызвать `send_user_confirmation()` | Получатель пользователь | Unit | `test_user_confirmation_uses_user_email` | `tests/unit/test_email_service.py` |
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
| PIPELINE-SUCCESS-001 | Полный pipeline успешно завершается | Временная SQLite, fake AI/email | Валидное обращение | Вызвать `ContactService.process_contact()` | Запись, AI, оба email и `completed` сохранены | Unit | `test_contact_service_processes_full_success` | `tests/unit/test_contact_service.py` |
| PIPELINE-AI-FALLBACK-001 | AI fallback не останавливает pipeline | Временная SQLite, fake AI fallback | Валидное обращение | Вызвать service | `ai_status=fallback`, письма отправлены, `completed_with_errors` | Unit | `test_contact_service_continues_after_ai_fallback` | `tests/unit/test_contact_service.py` |
| PIPELINE-AI-EXCEPTION-001 | Исключение AI превращается в fallback | Временная SQLite, AI raises | Валидное обращение | Вызвать service | Fallback сохранён, email-этап продолжается | Unit | `test_contact_service_converts_ai_exception_to_fallback` | `tests/unit/test_contact_service.py` |
| PIPELINE-OWNER-EMAIL-FAILED-001 | Ошибка письма владельцу не отменяет письмо пользователю | Временная SQLite, owner failed | Валидное обращение | Вызвать service | owner `failed`, user `sent`, `completed_with_errors` | Unit | `test_owner_email_failure_does_not_stop_user_email` | `tests/unit/test_contact_service.py` |
| PIPELINE-USER-EMAIL-FAILED-001 | Ошибка письма пользователю не отменяет письмо владельцу | Временная SQLite, user failed | Валидное обращение | Вызвать service | owner `sent`, user `failed`, `completed_with_errors` | Unit | `test_user_email_failure_does_not_cancel_owner_email` | `tests/unit/test_contact_service.py` |
| PIPELINE-EMAILS-FAILED-001 | Оба письма failed не роняют pipeline | Временная SQLite, оба email failed | Валидное обращение | Вызвать service | AI сохранён, оба email `failed`, `completed_with_errors` | Unit | `test_both_email_failures_keep_ai_result` | `tests/unit/test_contact_service.py` |
| PIPELINE-EMAIL-SKIPPED-001 | Skipped email считается частичной ошибкой | Временная SQLite, оба email skipped | Валидное обращение | Вызвать service | Email `skipped`, итог `completed_with_errors` | Unit | `test_skipped_email_results_in_completed_with_errors` | `tests/unit/test_contact_service.py` |
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
| REPOSITORY-EMAIL-UPDATE-002 | Статус письма пользователю обновляется отдельно | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-EMAIL-UPDATE-003 | Оба email-статуса можно обновить одной операцией | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-STATUS-001 | Общий статус обработки обновляется отдельно | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-METRICS-001 | Пустая база возвращает нулевые метрики | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-METRICS-002 | Несколько записей корректно агрегируются | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-METRICS-003 | Метрики не содержат персональные данные | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| REPOSITORY-ROLLBACK-001 | Ошибка сохранения выполняет rollback | Unit | Да | `tests/unit/test_contact_repository.py` | [x] |
| DATABASE-MIGRATION-001 | Alembic upgrade создаёт таблицу обращений | Integration | Да | `tests/integration/test_database.py` | [x] |
| DATABASE-MODEL-002 | Модель совместима с актуальной миграцией | Integration | Да | `tests/integration/test_database.py` | [x] |
| DATABASE-MIGRATION-002 | Alembic downgrade удаляет таблицу обращений | Integration | Да | `tests/integration/test_database.py` | [x] |
| AI-SCHEMA-001 | Валидный AI-результат принимается | Unit | Да | `tests/unit/test_ai_schemas.py` | [x] |
| AI-SCHEMA-002 | Неизвестные enum-значения отклоняются | Unit | Да | `tests/unit/test_ai_schemas.py` | [x] |
| AI-SCHEMA-003 | Слишком длинный summary отклоняется | Unit | Да | `tests/unit/test_ai_schemas.py` | [x] |
| AI-SCHEMA-004 | Пустой suggested reply отклоняется | Unit | Да | `tests/unit/test_ai_schemas.py` | [x] |
| AI-SCHEMA-005 | Fallback analysis соответствует схеме | Unit | Да | `tests/unit/test_ai_schemas.py` | [x] |
| AI-SCHEMA-006 | Fallback service result содержит статус | Unit | Да | `tests/unit/test_ai_schemas.py` | [x] |
| AI-SUCCESS-001 | Валидный structured output возвращает success | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-SUCCESS-002 | Системный промпт и комментарий передаются отдельно | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
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
| AI-PROMPT-INJECTION-001 | Prompt injection остаётся пользовательскими данными | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FAKE-001 | Fake success возвращает результат | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FAKE-002 | Fake fallback возвращает fallback | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FAKE-003 | Fake error имитирует исключение | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-FAKE-004 | Fake service не создаёт OpenAI-клиент | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-PROXY-001 | OpenAI SDK получает custom base_url | Unit | Да | `tests/unit/test_ai_service.py` | [x] |
| AI-LIVE-001 | Один контролируемый live-запрос через ProxyAPI | Manual | Нет | CLI manual | [x] |
| EMAIL-SCHEMA-001 | Валидное email-сообщение принимается | Unit | Да | `tests/unit/test_email_schemas.py` | [x] |
| EMAIL-SCHEMA-002 | Невалидные поля письма отклоняются | Unit | Да | `tests/unit/test_email_schemas.py` | [x] |
| EMAIL-SCHEMA-003 | Валидный результат отправки принимается | Unit | Да | `tests/unit/test_email_schemas.py` | [x] |
| EMAIL-SCHEMA-004 | Неизвестный email-статус отклоняется | Unit | Да | `tests/unit/test_email_schemas.py` | [x] |
| EMAIL-RENDER-OWNER-001 | Письмо владельцу рендерится | Unit | Да | `tests/unit/test_email_templates.py` | [x] |
| EMAIL-RENDER-USER-001 | Письмо пользователю не раскрывает внутренние данные | Unit | Да | `tests/unit/test_email_templates.py` | [x] |
| EMAIL-RENDER-OPTIONAL-001 | Optional-поля не выводят `None` | Unit | Да | `tests/unit/test_email_templates.py` | [x] |
| EMAIL-HTML-ESCAPE-001 | HTML комментария экранируется | Unit | Да | `tests/unit/test_email_templates.py` | [x] |
| EMAIL-TEXT-001 | Переносы строк комментария сохраняются | Unit | Да | `tests/unit/test_email_templates.py` | [x] |
| EMAIL-HTML-ESCAPE-002 | Suggested reply экранируется | Unit | Да | `tests/unit/test_email_templates.py` | [x] |
| EMAIL-RENDER-FALLBACK-001 | AI fallback отображается корректно | Unit | Да | `tests/unit/test_email_templates.py` | [x] |
| EMAIL-SEND-PAYLOAD-001 | Payload Resend формируется корректно | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-SEND-OWNER-001 | Письмо владельцу отправляется на `OWNER_EMAIL` | Unit | Да | `tests/unit/test_email_service.py` | [x] |
| EMAIL-SEND-USER-001 | Письмо пользователю отправляется на его email | Unit | Да | `tests/unit/test_email_service.py` | [x] |
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
| PIPELINE-OWNER-EMAIL-FAILED-001 | Ошибка письма владельцу не отменяет письмо пользователю | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
| PIPELINE-USER-EMAIL-FAILED-001 | Ошибка письма пользователю не отменяет письмо владельцу | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
| PIPELINE-EMAILS-FAILED-001 | Оба письма failed не роняют pipeline | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
| PIPELINE-EMAIL-SKIPPED-001 | Skipped email считается частичной ошибкой | Unit | Да | `tests/unit/test_contact_service.py` | [x] |
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

## Финальный checklist перед сдачей проекта

- [ ] Все автоматические тесты пройдены.
- [ ] Ручной health check выполнен.
- [ ] Миграции применяются из чистого состояния.
- [ ] AI live-вызов через ProxyAPI выполнен только при явном разрешении.
- [ ] Реальное тестовое письмо отправлено только при явном разрешении.
- [ ] Секреты отсутствуют в репозитории.
- [ ] README финального этапа описывает запуск, API, деплой и ограничения.
