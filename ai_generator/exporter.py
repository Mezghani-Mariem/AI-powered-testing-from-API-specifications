"""Atomic JSON exports. The executable test file contains only contract fields."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .schemas import TestSuite


def write_json(path: str | Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                                         prefix=".s5-", suffix=".tmp", delete=False) as stream:
            temp_path = Path(stream.name)
            stream.write(content)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def export_suite(suite: TestSuite, path: str | Path) -> None:
    # Validate again at the integration boundary, including unique IDs.
    validated = TestSuite.model_validate(suite.model_dump())
    write_json(path, validated.model_dump(mode="json"))

