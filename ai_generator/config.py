"""Explicit provider configuration; no implicit switch between live and mock."""

import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    api_key: SecretStr = SecretStr("")
    base_url: str = ""
    model: str = ""
    temperature: float = Field(default=0, ge=0, le=2)
    timeout: float = Field(default=60, gt=0, le=600)
    max_retries: int = Field(default=2, ge=0, le=5)
    response_format: Literal["json_object", "json_schema", "none"] = "json_object"
    max_tokens: int = Field(default=4096, ge=128, le=32768)

    @field_validator("base_url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        if not value:
            return value
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("LLM_BASE_URL must be an HTTP(S) base URL without credentials/query/fragment")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Use HTTPS for a remote LLM provider")
        return value.rstrip("/")

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> "LLMConfig":
        values = {**dotenv_values(env_file), **os.environ}
        mapping = {
            "api_key": "LLM_API_KEY", "base_url": "LLM_BASE_URL", "model": "LLM_MODEL",
            "temperature": "LLM_TEMPERATURE", "timeout": "LLM_TIMEOUT",
            "max_retries": "LLM_MAX_RETRIES", "response_format": "LLM_RESPONSE_FORMAT",
            "max_tokens": "LLM_MAX_TOKENS",
        }
        return cls(**{field: values[key] for field, key in mapping.items() if values.get(key) not in (None, "")})

    def public_settings(self) -> dict:
        return self.model_dump(exclude={"api_key", "base_url"})

