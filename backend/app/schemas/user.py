import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import Password


class UserRead(BaseModel):
    # from_attributes lets FastAPI build this directly from a SQLAlchemy User object.
    # hashed_password is simply not declared here, so it can never leak in a response.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    created_at: datetime


class UserUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class PasswordChange(BaseModel):
    current_password: str
    new_password: Password
