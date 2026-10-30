"""Strict JSON: no duplicate object keys, nonfinite numbers or code evaluation."""

import json
import math
from typing import Any

from .errors import OutputError


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise ValueError("Nonfinite JSON number")


def _float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("JSON float overflow")
    return number


def loads_json(raw: str, max_bytes: int = 2_000_000) -> Any:
    if len(raw.encode("utf-8")) > max_bytes:
        raise OutputError("JSON exceeds the size limit")
    try:
        return json.loads(raw, object_pairs_hook=_unique, parse_constant=_nonfinite, parse_float=_float)
    except (ValueError, RecursionError) as exc:
        raise OutputError("Invalid JSON (syntax, duplicate key or nonfinite number)") from exc


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))

