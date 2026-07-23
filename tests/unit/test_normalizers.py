import pytest

from app.schemas.normalizers import (
    normalize_email,
    normalize_multiline_text,
    normalize_name,
    normalize_phone,
    normalize_single_line_text,
)


@pytest.mark.parametrize(
    ("raw_value", "expected_value"),
    [
        ("   Иван    Иванов   ", "Иван Иванов"),
        ("\tАнна\nМария\t", "Анна Мария"),
    ],
    ids=[
        "имя очищается и повторяющиеся пробелы схлопываются",
        "переводы строк в однострочном поле становятся пробелом",
    ],
)
def test_single_line_text_is_normalized(raw_value: str, expected_value: str) -> None:
    """NORMALIZATION-001: однострочный текст очищается по краям и схлопывает пробелы."""
    assert normalize_single_line_text(raw_value) == expected_value
    assert normalize_name(raw_value) == expected_value


@pytest.mark.parametrize(
    ("raw_value", "expected_value"),
    [
        ("  User@Example.COM  ", "user@example.com"),
    ],
    ids=["email очищается по краям и приводится к нижнему регистру"],
)
def test_email_is_normalized(raw_value: str, expected_value: str) -> None:
    """NORMALIZATION-EMAIL-001: email очищается по краям и приводится к нижнему регистру."""
    assert normalize_email(raw_value) == expected_value


@pytest.mark.parametrize(
    ("raw_value", "expected_value"),
    [
        ("8 (999) 123-45-67", "+79991234567"),
        ("+7 999 123 45 67", "+79991234567"),
        ("+49 30 123456", "+4930123456"),
        ("  +7 999 123 45 67  ", "+79991234567"),
    ],
    ids=[
        "российский номер с восьмеркой приводится к плюс семь",
        "российский номер с плюс семь очищается от пробелов",
        "международный номер сохраняет страновой код",
        "телефон очищается от пробелов по краям",
    ],
)
def test_phone_is_normalized(raw_value: str, expected_value: str) -> None:
    """NORMALIZATION-PHONE-001: телефон приводится к единому формату + и цифры."""
    assert normalize_phone(raw_value) == expected_value


@pytest.mark.parametrize(
    ("raw_value", "expected_value"),
    [
        ("   Первая строка.\n\nВторая    строка.   ", "Первая строка.\n\nВторая    строка."),
    ],
    ids=["комментарий очищается только по краям"],
)
def test_multiline_text_keeps_internal_formatting(raw_value: str, expected_value: str) -> None:
    """NORMALIZATION-COMMENT-001: комментарий сохраняет внутренние пробелы и абзацы."""
    assert normalize_multiline_text(raw_value) == expected_value


@pytest.mark.parametrize(
    "raw_value",
    [
        "phone text",
        "+7 999 123 * 45",
    ],
    ids=[
        "телефон с буквами отклоняется нормализатором",
        "телефон с посторонним спецсимволом отклоняется нормализатором",
    ],
)
def test_phone_normalizer_rejects_forbidden_characters(raw_value: str) -> None:
    """VALIDATION-PHONE-001: нормализатор телефона отклоняет недопустимые символы."""
    with pytest.raises(ValueError):
        normalize_phone(raw_value)
