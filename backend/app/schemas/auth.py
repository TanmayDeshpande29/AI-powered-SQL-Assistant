from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.security import BCRYPT_MAX_BYTES


def _check_password_bytes(value: str) -> str:
    if len(value.encode()) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must be at most {BCRYPT_MAX_BYTES} bytes")
    return value


def _normalize_email(value: str) -> str:
    return value.strip().lower()


Password = Annotated[str, Field(min_length=8), AfterValidator(_check_password_bytes)]
NormalizedEmail = Annotated[EmailStr, AfterValidator(_normalize_email)]


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: NormalizedEmail
    password: Password


class LoginRequest(BaseModel):
    email: NormalizedEmail
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
