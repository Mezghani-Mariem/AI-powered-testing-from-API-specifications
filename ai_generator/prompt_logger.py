"""Opt-in JSONL trace. Content logging is a separate, explicit option."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .prompt_builder import PROMPT_VERSION


class PromptLogger:
    def __init__(self, path: str | Path | None = None, *, log_content: bool = False,
                 secrets: tuple[str, ...] = ()):
        self.path = Path(path) if path else None
        self.log_content = log_content
        self.secrets = tuple(secret for secret in secrets if secret)

    def record(self, *, model: str, mode: str, settings: dict, spec_hash: str,
               operation: str, messages: list[dict], raw_response: str | None,
               validation: list[dict], error: str | None, attempts: int,
               duration_seconds: float) -> None:
        if self.path is None:
            return
        event: dict[str, Any] = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "prompt_version": PROMPT_VERSION, "model": model, "mode": mode,
            "llm_parameters": settings, "spec_sha256": spec_hash, "operation": operation,
            "attempts": attempts, "duration_seconds": duration_seconds,
            "validation": validation, "error": error, "content_logged": self.log_content,
        }
        if self.log_content:
            event.update(messages=messages, response=raw_response)
        # The active provider API key is never written, even if echoed in source data.
        line = json.dumps(event, ensure_ascii=False, allow_nan=False)
        for secret in self.secrets:
            line = line.replace(secret, "[REDACTED]").replace(json.dumps(secret)[1:-1], "[REDACTED]")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line + "\n")

