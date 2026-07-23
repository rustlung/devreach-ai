from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.schemas.normalizers import (
    normalize_email,
    normalize_multiline_text,
    normalize_name,
    normalize_phone,
)

NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 80
PHONE_MIN_DIGITS = 8
PHONE_MAX_DIGITS = 15
EMAIL_MAX_LENGTH = 254
COMMENT_MIN_LENGTH = 5
COMMENT_MAX_LENGTH = 5000


class ContactRequestCreate(BaseModel):
    name: str
    phone: str
    email: Annotated[EmailStr, Field(max_length=EMAIL_MAX_LENGTH)]
    comment: str
    website: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name_before_validation(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Имя должно быть строкой")
        return normalize_name(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if len(value) < NAME_MIN_LENGTH:
            raise ValueError(f"Имя должно содержать минимум {NAME_MIN_LENGTH} символа")
        if len(value) > NAME_MAX_LENGTH:
            raise ValueError(f"Имя должно быть не длиннее {NAME_MAX_LENGTH} символов")
        if not any(character.isalpha() for character in value):
            raise ValueError("Имя должно содержать хотя бы одну букву")
        if value[0] in " -'" or value[-1] in " -'":
            raise ValueError("Имя не может начинаться или заканчиваться пробелом, дефисом или апострофом")

        previous_character = ""
        for character in value:
            if character.isalpha() or character in " -'":
                if character in "-'" and previous_character in " -'":
                    raise ValueError("Разделители в имени не должны идти подряд или рядом с пробелом")
                if character == " " and previous_character in "-'":
                    raise ValueError("Пробел не должен стоять рядом с дефисом или апострофом")
                previous_character = character
                continue
            if character.isdigit():
                raise ValueError("Имя не должно содержать цифры")
            raise ValueError("Имя содержит недопустимые специальные символы")

        return value

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone_before_validation(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Телефон должен быть строкой")
        return normalize_phone(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not value:
            raise ValueError("Телефон обязателен")
        if not value.startswith("+") or not value[1:].isdigit():
            raise ValueError("Телефон должен быть в формате + и цифры")

        digits_count = len(value) - 1
        if digits_count < PHONE_MIN_DIGITS:
            raise ValueError(f"Телефон должен содержать минимум {PHONE_MIN_DIGITS} цифр")
        if digits_count > PHONE_MAX_DIGITS:
            raise ValueError(f"Телефон должен содержать не больше {PHONE_MAX_DIGITS} цифр")
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_before_validation(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Email должен быть строкой")
        normalized_email = normalize_email(value)
        if not normalized_email:
            raise ValueError("Email обязателен")
        if any(character.isspace() for character in normalized_email):
            raise ValueError("Email не должен содержать внутренние пробелы")
        if len(normalized_email) > EMAIL_MAX_LENGTH:
            raise ValueError(f"Email должен быть не длиннее {EMAIL_MAX_LENGTH} символов")
        return normalized_email

    @field_validator("comment", mode="before")
    @classmethod
    def normalize_comment_before_validation(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Комментарий должен быть строкой")
        return normalize_multiline_text(value)

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, value: str) -> str:
        if not value:
            raise ValueError("Комментарий обязателен")
        if len(value) < COMMENT_MIN_LENGTH:
            raise ValueError(f"Комментарий должен содержать минимум {COMMENT_MIN_LENGTH} символов")
        if len(value) > COMMENT_MAX_LENGTH:
            raise ValueError(f"Комментарий должен быть не длиннее {COMMENT_MAX_LENGTH} символов")
        return value

    @field_validator("website", mode="before")
    @classmethod
    def normalize_website_before_validation(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Служебное поле должно быть строкой")
        return value.strip()

    @model_validator(mode="after")
    def reject_filled_honeypot(self) -> "ContactRequestCreate":
        if self.website:
            raise ValueError("Служебное поле должно оставаться пустым")
        return self
