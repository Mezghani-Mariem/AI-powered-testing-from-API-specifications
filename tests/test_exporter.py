import json

import pytest

from ai_generator.exporter import export_suite, write_json
from ai_generator.schemas import TestCase, TestSuite


def test_exact_contract_export(tmp_path, cases):
    suite = TestSuite(schema_version="1.0", tests=[TestCase.model_validate(cases[0])])
    path = tmp_path / "nested" / "generated_tests.json"
    export_suite(suite, path)
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert set(data) == {"schema_version", "tests"}
    assert set(data["tests"][0]) == set(cases[0])
    assert data["tests"][0]["body"] is None
    assert TestSuite.model_validate(data) == suite
    assert not list(path.parent.glob("*.tmp"))


def test_write_nonfinite_does_not_damage_existing_file(tmp_path):
    path = tmp_path / "existing.json"
    path.write_text("original", encoding="utf-8")
    with pytest.raises(ValueError):
        write_json(path, {"value": float("nan")})
    assert path.read_text(encoding="utf-8") == "original"
