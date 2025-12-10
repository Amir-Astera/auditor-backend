# app/auth/schemas.py
from pydantic import BaseModel, EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserBase(BaseModel):
    id: str
    email: EmailStr | None = None
    full_name: str | None = None
    telegram_phone: str | None = None
    telegram_user_id: int | None = None
    is_admin: bool
    is_active: bool

    class Config:
        from_attributes = True
