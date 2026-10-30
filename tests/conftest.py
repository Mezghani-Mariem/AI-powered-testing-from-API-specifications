import copy
import json
from pathlib import Path

import httpx
import pytest

from ai_generator.openapi_parser import OpenAPIParser

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "examples" / "sample_openapi.json"


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network is forbidden in the standard pytest suite")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)


@pytest.fixture
def spec():
    return OpenAPIParser().parse(SPEC)


@pytest.fixture
def document():
    return json.loads(SPEC.read_text(encoding="utf-8"))


@pytest.fixture
def save_spec(tmp_path):
    def save(document, suffix=".json"):
        import yaml
        path = tmp_path / ("spec" + suffix)
        path.write_text(json.dumps(document) if suffix == ".json" else yaml.safe_dump(document), encoding="utf-8")
        return path
    return save


@pytest.fixture
def cases():
    data = json.loads((ROOT / "ai_generator" / "fixtures" / "products_recording.json").read_text(encoding="utf-8"))
    return copy.deepcopy([case for operation in data["operations"].values() for case in operation["tests"]])
