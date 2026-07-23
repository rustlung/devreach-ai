import re


SINGLE_LINE_WHITESPACE_RE = re.compile(r"\s+")
PHONE_ALLOWED_RE = re.compile(r"^[\d\s()+-]+$")


def normalize_single_line_text(value: str) -> str:
    return SINGLE_LINE_WHITESPACE_RE.sub(" ", value.strip())


def normalize_name(value: str) -> str:
    # Имя валидируется уже после схлопывания пробелов, чтобы `Иван    Иванов`
    # проверялось и сохранялось как один понятный вариант.
    return normalize_single_line_text(value)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_multiline_text(value: str) -> str:
    # В комментарии сохраняем внутренние пробелы, переносы и абзацы:
    # это пользовательский смысловой текст, а не однострочное поле.
    return value.strip()


def normalize_phone(value: str) -> str:
    raw_phone = value.strip()
    if not raw_phone:
        return ""

    if not PHONE_ALLOWED_RE.fullmatch(raw_phone):
        raise ValueError("Телефон может содержать только цифры, пробелы, дефисы, скобки и ведущий плюс")

    if raw_phone.count("+") > 1 or ("+" in raw_phone and not raw_phone.startswith("+")):
        raise ValueError("Символ + допускается только в начале телефона")

    has_leading_plus = raw_phone.startswith("+")
    digits = re.sub(r"\D", "", raw_phone)

    # Российская восьмёрка часто вводится как локальный префикс; приводим её
    # к международному формату +7, чтобы дальнейшая обработка была единообразной.
    if len(digits) == 11 and digits.startswith("8"):
        return "+7" + digits[1:]

    if len(digits) == 11 and digits.startswith("7"):
        return "+" + digits

    if has_leading_plus:
        return "+" + digits

    return "+" + digits
