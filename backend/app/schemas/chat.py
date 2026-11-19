import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(value: str) -> str:
    """Buang karakter kontrol dan rapikan spasi; teks pengguna tidak boleh membawa kontrol terminal/log."""
    return " ".join(_CONTROL_CHARS.sub(" ", value).split())


class ChatTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(max_length=1000)

    @field_validator("content")
    @classmethod
    def _sanitize(cls, value: str) -> str:
        return _clean(value)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=500)
    history: list[ChatTurn] = Field(default_factory=list, max_length=6)
    # Skenario kapasitas bulanan (ribu penumpang) yang sedang dipilih pengguna di dashboard.
    ambang_kapasitas: float | None = Field(default=None, gt=0, le=1_000_000, allow_inf_nan=False)

    @field_validator("message")
    @classmethod
    def _sanitize_message(cls, value: str) -> str:
        cleaned = _clean(value)
        if not cleaned:
            raise ValueError("message must not be blank")
        return cleaned


Status = Literal["aman", "waspada", "kritis", "belum_ditentukan"]


class ChatAnswer(BaseModel):
    intent: str
    # Teks polos. Server tidak pernah mengirim HTML; klien wajib menampilkannya sebagai teks.
    answer: str = Field(max_length=700)
    bullets: list[str] = Field(default_factory=list, max_length=8)
    status: Status | None = None
    source: Literal["rules", "ollama"] = "rules"
    suggestions: list[str] = Field(default_factory=list, max_length=4)


class ChatResponse(BaseModel):
    data: ChatAnswer
    meta: dict
