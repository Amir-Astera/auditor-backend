"""Pydantic schemas for authentication endpoints."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def validate_password_length(password: str) -> str:
    """
    Валидация длины пароля.
    Field уже проверяет min_length/max_length, эта функция просто возвращает значение.
    """
    return password 


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=72,  # Примерная длина для ASCII
        description="Административный пароль (минимум 8 символов, максимум 72 байта)"
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_length(v)


class TelegramLoginRequest(BaseModel):
    phone: str = Field(description="Номер телефона в формате Telegram")
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_length(v)


class UserCreateRequest(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    password: str = Field(
        min_length=8,
        max_length=72,
        description="Пароль (минимум 8 символов, максимум 72 байта)"
    )
    telegram_phone: str | None = None
    telegram_user_id: int | None = None
    is_admin: bool = False

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_length(v)


class UserBase(BaseModel):
    id: UUID
    email: EmailStr | None = None
    full_name: str | None = None
    telegram_phone: str | None = None
    telegram_user_id: int | None = None
    is_admin: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
