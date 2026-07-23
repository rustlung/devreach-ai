import pytest
from pydantic import ValidationError

from app.schemas.contact import ContactRequestCreate
from tests.conftest import readable_test_id


def valid_contact_data(**overrides) -> dict:
    data = {
        "name": "Иван Иванов",
        "phone": "+7 999 123 45 67",
        "email": "user@example.com",
        "comment": "Здравствуйте, хочу обсудить проект.",
    }
    data.update(overrides)
    return data


def validation_messages(error: ValidationError) -> str:
    return " ".join(str(item["msg"]) for item in error.errors())


@pytest.mark.parametrize(
    ("raw_name", "expected_name"),
    [
        ("Иван", "Иван"),
        ("Иван Иванов", "Иван Иванов"),
        ("   Иван    Иванов   ", "Иван Иванов"),
        ("Анна-Мария", "Анна-Мария"),
        ("O'Connor", "O'Connor"),
        ("Jean-Pierre", "Jean-Pierre"),
        ("Мария де Ла Крус", "Мария де Ла Крус"),
    ],
    ids=[
        "обычное русское имя допустимо",
        "имя и фамилия допустимы",
        "повторяющиеся пробелы в имени схлопываются",
        "дефис в имени допустим",
        "апостроф в имени допустим",
        "латинское имя допустимо",
        "несколько частей имени допустимы",
    ],
)
def test_valid_name_is_accepted(raw_name: str, expected_name: str) -> None:
    """VALIDATION-NAME-001: допустимые имена принимаются и возвращаются нормализованными."""
    contact = ContactRequestCreate(**valid_contact_data(name=raw_name))

    assert contact.name == expected_name


@pytest.mark.parametrize(
    ("raw_name", "expected_error_part"),
    [
        ("Иван123", "цифры"),
        ("user_name", "недопустимые специальные символы"),
        ("Иван@", "недопустимые специальные символы"),
        ("   ", "минимум"),
        ("A", "минимум"),
        ("А" * 81, "не длиннее"),
        ("Иван--Петров", "Разделители"),
        ("-Иван", "не может начинаться"),
        ("Иван-", "не может начинаться или заканчиваться"),
        ("Иван  -  Петров", "Разделители"),
    ],
    ids=[
        "цифра в имени запрещена",
        "подчеркивание в имени запрещено",
        "собака в имени запрещена",
        "имя только из пробелов запрещено",
        "слишком короткое имя запрещено",
        "слишком длинное имя запрещено",
        "разделители подряд в имени запрещены",
        "разделитель в начале имени запрещен",
        "разделитель в конце имени запрещен",
        "разделитель рядом с пробелом запрещен",
    ],
)
def test_invalid_name_is_rejected(raw_name: str, expected_error_part: str) -> None:
    """VALIDATION-NAME-002: недопустимые имена отклоняются с понятной причиной."""
    with pytest.raises(ValidationError) as exc_info:
        ContactRequestCreate(**valid_contact_data(name=raw_name))

    assert expected_error_part in validation_messages(exc_info.value)


@pytest.mark.parametrize(
    ("raw_phone", "expected_phone"),
    [
        ("8 (999) 123-45-67", "+79991234567"),
        ("+7 999 123 45 67", "+79991234567"),
        ("+7 (999) 123-45-67", "+79991234567"),
        ("+49 30 123456", "+4930123456"),
        ("  +7 999 123 45 67  ", "+79991234567"),
    ],
    ids=[
        "российский телефон с восьмеркой нормализуется",
        "российский телефон с плюс семь нормализуется",
        "российский телефон со скобками и дефисами нормализуется",
        "международный телефон нормализуется",
        "пробелы по краям телефона удаляются",
    ],
)
def test_valid_phone_is_accepted(raw_phone: str, expected_phone: str) -> None:
    """VALIDATION-PHONE-002: допустимые телефоны принимаются и нормализуются."""
    contact = ContactRequestCreate(**valid_contact_data(phone=raw_phone))

    assert contact.phone == expected_phone


@pytest.mark.parametrize(
    ("raw_phone", "expected_error_part"),
    [
        ("+7 phone", "может содержать"),
        ("+7 999 123 * 45", "может содержать"),
        ("+123", "минимум"),
        ("+" + "1" * 16, "не больше"),
        ("", "обязателен"),
    ],
    ids=[
        "буквы в телефоне запрещены",
        "посторонние спецсимволы в телефоне запрещены",
        "слишком короткий телефон запрещен",
        "слишком длинный телефон запрещен",
        "пустой телефон запрещен",
    ],
)
def test_invalid_phone_is_rejected(raw_phone: str, expected_error_part: str) -> None:
    """VALIDATION-PHONE-003: недопустимые телефоны отклоняются с понятной причиной."""
    with pytest.raises(ValidationError) as exc_info:
        ContactRequestCreate(**valid_contact_data(phone=raw_phone))

    assert expected_error_part in validation_messages(exc_info.value)


@pytest.mark.parametrize(
    ("raw_email", "expected_email"),
    [
        ("user@example.com", "user@example.com"),
        ("  user@example.com  ", "user@example.com"),
        ("User@Example.COM", "user@example.com"),
    ],
    ids=[
        "корректный email допустим",
        "пробелы по краям email удаляются",
        "email приводится к нижнему регистру",
    ],
)
def test_valid_email_is_accepted(raw_email: str, expected_email: str) -> None:
    """VALIDATION-EMAIL-001: допустимый email принимается и нормализуется."""
    contact = ContactRequestCreate(**valid_contact_data(email=raw_email))

    assert str(contact.email) == expected_email


@pytest.mark.parametrize(
    ("raw_email", "expected_error_part"),
    [
        ("user name@example.com", "внутренние пробелы"),
        ("not-email", "valid email"),
        ("", "обязателен"),
    ],
    ids=[
        "внутренний пробел в email запрещен",
        "некорректный формат email запрещен",
        "пустой email запрещен",
    ],
)
def test_invalid_email_is_rejected(raw_email: str, expected_error_part: str) -> None:
    """VALIDATION-EMAIL-002: недопустимый email отклоняется с понятной причиной."""
    with pytest.raises(ValidationError) as exc_info:
        ContactRequestCreate(**valid_contact_data(email=raw_email))

    assert expected_error_part in validation_messages(exc_info.value)


@pytest.mark.parametrize(
    ("raw_comment", "expected_comment"),
    [
        ("Хочу обсудить проект.", "Хочу обсудить проект."),
        ("   Хочу обсудить проект.   ", "Хочу обсудить проект."),
        ("Первая    строка.", "Первая    строка."),
        ("Первая строка.\nВторая строка.", "Первая строка.\nВторая строка."),
        ("Первая строка.\n\nВторая строка.", "Первая строка.\n\nВторая строка."),
    ],
    ids=[
        "корректный комментарий допустим",
        "пробелы по краям комментария удаляются",
        "внутренние повторяющиеся пробелы комментария сохраняются",
        "переносы строк комментария сохраняются",
        "абзацы комментария сохраняются",
    ],
)
def test_valid_comment_is_accepted(raw_comment: str, expected_comment: str) -> None:
    """VALIDATION-COMMENT-001: допустимый комментарий принимается без изменения форматирования."""
    contact = ContactRequestCreate(**valid_contact_data(comment=raw_comment))

    assert contact.comment == expected_comment


@pytest.mark.parametrize(
    ("raw_comment", "expected_error_part"),
    [
        ("   ", "обязателен"),
        ("\n\n\n", "обязателен"),
        ("abc", "минимум"),
        ("А" * 5001, "не длиннее"),
    ],
    ids=[
        "комментарий только из пробелов запрещен",
        "комментарий только из переносов запрещен",
        "слишком короткий комментарий запрещен",
        "слишком длинный комментарий запрещен",
    ],
)
def test_invalid_comment_is_rejected(raw_comment: str, expected_error_part: str) -> None:
    """VALIDATION-COMMENT-002: недопустимый комментарий отклоняется с понятной причиной."""
    with pytest.raises(ValidationError) as exc_info:
        ContactRequestCreate(**valid_contact_data(comment=raw_comment))

    assert expected_error_part in validation_messages(exc_info.value)


@readable_test_id("полностью валидное обращение создает схему")
def test_valid_contact_request_is_created(_case_id) -> None:
    """VALIDATION-CONTACT-001: полностью валидное обращение создаёт входную схему."""
    contact = ContactRequestCreate(**valid_contact_data())

    assert contact.name == "Иван Иванов"
    assert contact.phone == "+79991234567"
    assert str(contact.email) == "user@example.com"
    assert contact.comment == "Здравствуйте, хочу обсудить проект."


@readable_test_id("все поля обращения возвращаются нормализованными")
def test_contact_request_returns_normalized_fields(_case_id) -> None:
    """NORMALIZATION-CONTACT-001: все поля обращения возвращаются нормализованными."""
    contact = ContactRequestCreate(
        **valid_contact_data(
            name="   Иван    Иванов   ",
            phone="8 (999) 123-45-67",
            email="  User@Example.COM  ",
            comment="   Первая строка.\n\nВторая    строка.   ",
        )
    )

    assert contact.name == "Иван Иванов"
    assert contact.phone == "+79991234567"
    assert str(contact.email) == "user@example.com"
    assert contact.comment == "Первая строка.\n\nВторая    строка."


@readable_test_id("ошибка одного поля содержит понятную информацию")
def test_single_field_error_contains_clear_message(_case_id) -> None:
    """VALIDATION-CONTACT-002: ошибка одного поля содержит понятную информацию."""
    with pytest.raises(ValidationError) as exc_info:
        ContactRequestCreate(**valid_contact_data(name="Иван123"))

    assert "Имя не должно содержать цифры" in validation_messages(exc_info.value)


@readable_test_id("внутренние пробелы комментария не изменяются")
def test_comment_internal_spaces_are_not_changed(_case_id) -> None:
    """NORMALIZATION-COMMENT-002: исходные внутренние пробелы комментария сохраняются."""
    contact = ContactRequestCreate(**valid_contact_data(comment="Первая    строка.\n\nВторая    строка."))

    assert contact.comment == "Первая    строка.\n\nВторая    строка."


@readable_test_id("лишние пробелы в имени не попадают в итоговые данные")
def test_extra_name_spaces_are_not_returned(_case_id) -> None:
    """NORMALIZATION-NAME-001: лишние пробелы в имени не попадают в итоговые данные."""
    contact = ContactRequestCreate(**valid_contact_data(name="   Иван    Иванов   "))

    assert contact.name == "Иван Иванов"


@readable_test_id("заполненный honeypot отклоняет обращение")
def test_filled_honeypot_is_rejected(_case_id) -> None:
    """VALIDATION-HONEYPOT-001: заполненное служебное поле считается признаком спама."""
    with pytest.raises(ValidationError) as exc_info:
        ContactRequestCreate(**valid_contact_data(website="https://spam.test"))

    assert "Служебное поле должно оставаться пустым" in validation_messages(exc_info.value)
