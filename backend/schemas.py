"""Pydantic schemas: پشکنینی ئەو داتایەی دێتە ناو API ـەکە."""
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=160)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class LoginIn(BaseModel):
    email: str = Field(max_length=160)
    password: str = Field(max_length=128)

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.strip().lower()


class PredictIn(BaseModel):
    features: dict[str, Any]
    asked_price: float | None = Field(default=None, ge=0, le=100000)
    phone_id: str | None = Field(default=None, max_length=120)
    phone_name: str | None = Field(default=None, max_length=160)
    save: bool = True
    explain: bool = True
    similar: bool = True


class CompareItem(BaseModel):
    features: dict[str, Any]
    phone_id: str | None = Field(default=None, max_length=120)
    phone_name: str | None = Field(default=None, max_length=160)
    asked_price: float | None = Field(default=None, ge=0, le=100000)


class CompareIn(BaseModel):
    items: list[CompareItem] = Field(min_length=2, max_length=3)


class UserUpdate(BaseModel):
    role: Literal["user", "admin"] | None = None
    is_active: bool | None = None
