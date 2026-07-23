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

## Финальный checklist перед сдачей проекта

- [ ] Все автоматические тесты пройдены.
- [ ] Ручной health check выполнен.
- [ ] Миграции применяются из чистого состояния.
- [ ] OpenAI live-вызов выполнен только при явном разрешении.
- [ ] Реальное тестовое письмо отправлено только при явном разрешении.
- [ ] Секреты отсутствуют в репозитории.
- [ ] README финального этапа описывает запуск, API, деплой и ограничения.
