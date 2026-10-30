import copy
import json

from ai_generator.errors import LLMError
from ai_generator.llm_client import LLMResult, MockLLMClient
from ai_generator.prompt_logger import PromptLogger
from ai_generator.test_generator import TestGenerator

from conftest import ROOT, SPEC


class FakeClient:
    mode = "live"
    model = "offline-fake"
    attempts = 0

    def __init__(self, items):
        self.items = items

    def generate(self, messages, operation, spec, target):
        self.attempts += 1
        data = {"schema_version": "1.0", "tests": copy.deepcopy(self.items.get(operation.key, []))}
        return LLMResult(data, json.dumps(data), 1, 0, self.model, self.mode)


def test_mock_end_to_end_reproducible(tmp_path):
    first = TestGenerator(MockLLMClient()).generate(SPEC, tmp_path / "a" / "tests.json")
    second = TestGenerator(MockLLMClient()).generate(SPEC, tmp_path / "b" / "tests.json")
    assert (tmp_path / "a" / "tests.json").read_bytes() == (tmp_path / "b" / "tests.json").read_bytes()
    assert first.suite == second.suite
    assert [test.test_id for test in first.suite.tests] == [f"TC_{index:03d}" for index in range(1, 7)]
    metrics = first.report["metrics"]
    assert metrics["validated_tests"] == metrics["proposed_tests"] == 6
    assert metrics["structural_validity_percent"] == metrics["semantic_acceptance_percent"] == 100
    assert metrics["operation_generation_coverage_percent"] == 100
    assert metrics["llm_attempts"] == 0 and metrics["mock_playbacks"] == 2
    assert metrics["category_distribution"] == {"positive": 2, "negative": 2, "boundary": 2}


def test_two_recorded_datasets(tmp_path):
    path = ROOT / "ai_generator" / "fixtures" / "products_recording_b.json"
    result = TestGenerator(MockLLMClient(path)).generate(SPEC, tmp_path / "tests.json")
    assert len(result.suite.tests) == 6
    assert result.suite.tests[0].test_type == "boundary"


def test_rejections_hypotheses_duplicates_and_metrics(tmp_path, cases):
    valid = cases[0]
    duplicate = {**valid, "test_id": "other", "name": "same behavior renamed"}
    hypothetical = {**valid, "path_params": {"id": 12}, "expected_body": None}
    malformed = {**valid, "method": "not-a-method"}
    wrong_endpoint = {**valid, "endpoint": "/absent"}
    client = FakeClient({"GET /products/{id}": [valid, duplicate, hypothetical, malformed, wrong_endpoint]})
    result = TestGenerator(client).generate(SPEC, tmp_path / "tests.json")
    metrics = result.report["metrics"]
    assert metrics["proposed_tests"] == 5
    assert metrics["validated_tests"] == 1
    assert metrics["rejected_tests"] == 3 and metrics["duplicates"] == 1
    assert metrics["structural_validity_percent"] == 80
    assert metrics["semantic_acceptance_percent"] == 50
    assert metrics["operation_generation_coverage_percent"] == 50
    hypotheses = json.loads(result.hypotheses_path.read_text(encoding="utf-8"))
    assert hypotheses["executable"] is False and len(hypotheses["scenarios"]) == 1
    assert hypotheses["scenarios"][0]["candidate"]["path_params"] == {"id": 12}


def test_per_operation_scope(tmp_path, cases):
    result = TestGenerator(FakeClient({"GET /products/{id}": [cases[3]]})).generate(SPEC, tmp_path / "tests.json")
    assert not result.suite.tests
    assert result.report["metrics"]["semantically_rejected_tests"] == 1


def test_failures_recorded_no_silent_fallback(tmp_path):
    class Failing(FakeClient):
        def generate(self, *args):
            self.attempts += 3
            raise LLMError("Timed out; 3 attempts")
    result = TestGenerator(Failing({})).generate(SPEC, tmp_path / "tests.json")
    assert result.report["status"] == "partial_error"
    assert len(result.report["operation_failures"]) == 2
    assert result.report["metrics"]["llm_attempts"] == 6
    assert result.report["metrics"]["structural_validity_percent"] is None
    assert not result.suite.tests


def test_logging_privacy_and_optional_content(tmp_path):
    for enabled in (False, True):
        path = tmp_path / f"log-{enabled}.jsonl"
        logger = PromptLogger(path, log_content=enabled, secrets=("private-key",))
        logger.record(model="test", mode="mock", settings={}, spec_hash="abc", operation="GET /x",
                      messages=[{"content": "private-key sensitive-description"}], raw_response="private-key",
                      validation=[], error=None, attempts=0, duration_seconds=0)
        text = path.read_text(encoding="utf-8")
        event = json.loads(text)
        assert "private-key" not in text
        assert event["content_logged"] is enabled
        assert ("sensitive-description" in text) is enabled
        assert ("response" in event) is enabled


def test_logging_disabled(tmp_path):
    result = TestGenerator(MockLLMClient()).generate(SPEC, tmp_path / "tests.json")
    assert result.suite.tests
    assert not list(tmp_path.glob("*.jsonl"))


def test_log_success_validation(tmp_path):
    path = tmp_path / "trace.jsonl"
    TestGenerator(MockLLMClient(), logger=PromptLogger(path)).generate(SPEC, tmp_path / "tests.json")
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(events) == 2
    assert all(len(event["spec_sha256"]) == 64 and len(event["validation"]) == 3 for event in events)
