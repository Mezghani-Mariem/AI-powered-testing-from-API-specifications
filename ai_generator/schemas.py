"""The exact v1.0 integration contract. Internal metadata lives elsewhere."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class TestCase(ContractModel):
    __test__ = False
    test_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"]
    endpoint: str
    test_type: Literal["positive", "negative", "boundary"]
    path_params: dict[str, JsonValue]
    query_params: dict[str, JsonValue]
    headers: dict[str, str]
    body: JsonValue
    expected_status: int = Field(ge=100, le=599)
    expected_body: dict[str, JsonValue] | None

    @field_validator("endpoint")
    @classmethod
    def relative_endpoint(cls, value: str) -> str:
        if not value.startswith("/") or value.startswith("//") or re.search(r"[\s?#]", value):
            raise ValueError("endpoint must be a relative OpenAPI path, without query or fragment")
        return value

    @field_validator("headers")
    @classmethod
    def valid_headers(cls, value: dict[str, str]) -> dict[str, str]:
        if len({key.lower() for key in value}) != len(value):
            raise ValueError("Duplicate case-insensitive header")
        for key, item in value.items():
            if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key) or "\r" in item or "\n" in item:
                raise ValueError("Invalid HTTP header")
        return value


class TestSuite(ContractModel):
    __test__ = False
    schema_version: Literal["1.0"]
    tests: list[TestCase]

    @model_validator(mode="after")
    def unique_ids(self) -> "TestSuite":
        ids = [case.test_id for case in self.tests]
        if len(ids) != len(set(ids)):
            raise ValueError("test_id values must be unique")
        return self

