from pathlib import Path

import pytest

from ai_generator.audit import audit_generation
from ai_generator.cli import main
from ai_generator.exporter import write_json
from ai_generator.json_utils import loads_json
from ai_generator.llm_client import MockLLMClient
from ai_generator.test_generator import TestGenerator

from conftest import ROOT, SPEC


@pytest.fixture
def observed(tmp_path):
    data = loads_json((ROOT / "tests" / "fixtures" / "ollama_observed.json").read_text(encoding="utf-8"))
    paths = (SPEC, tmp_path / "tests.json", tmp_path / "report.json", tmp_path / "hypotheses.json")
    for path, key in zip(paths[1:], ("tests", "report", "hypotheses")):
        write_json(path, data[key])
    return data, paths


def test_observed_four_exports_and_two_hypotheses_are_consistent(observed):
    _, paths = observed
    result = audit_generation(*paths)
    assert result["valid"] is True
    assert len(result["exported_tests"]) == 4
    assert len(result["hypothetical_scenarios"]) == 2
    assert all(item["outcome"] == "accepted" for item in result["exported_tests"])
    assert all(item["reasons"] == ["Concrete response assertion values lack scenario evidence"]
               for item in result["hypothetical_scenarios"])
    assert result["warnings"]  # Older reports cannot prove file association historically.


@pytest.mark.parametrize("field,value", [
    ("validated_tests", 6), ("hypothetical_tests", 0), ("proposed_tests", 7),
    ("semantic_acceptance_percent", 100), ("operations_covered", 1),
    ("duplicates", 1), ("rejected_tests", 0), ("structurally_rejected_tests", 1),
    ("llm_attempts", -1), ("generation_seconds", -1),
])
def test_inconsistent_metrics_fail_audit(observed, field, value):
    data, paths = observed
    data["report"]["metrics"][field] = value
    write_json(paths[2], data["report"])
    assert audit_generation(*paths)["valid"] is False


def test_missing_hypothesis_is_detected(observed):
    data, paths = observed
    data["hypotheses"]["scenarios"].pop()
    write_json(paths[3], data["hypotheses"])
    assert audit_generation(*paths)["valid"] is False


def test_changed_reason_and_mode_are_detected(observed):
    data, paths = observed
    data["hypotheses"]["mode"] = "mock"
    data["hypotheses"]["scenarios"][0]["reasons"] = ["Resource does not exist"]
    write_json(paths[3], data["hypotheses"])
    result = audit_generation(*paths)
    assert result["valid"] is False
    assert any(x["check"] == "hypothesis_reasons_match" and not x["passed"] for x in result["checks"])


def test_unsupported_assertions_stay_hypothetical_without_changing_files(observed):
    _, paths = observed
    before = {path: path.read_bytes() for path in paths}
    result = audit_generation(*paths)
    assert result["valid"] is True
    assert all(item["outcome"] == "hypothetical" for item in result["hypothetical_scenarios"])
    assert before == {path: path.read_bytes() for path in paths}


def test_historical_reports_do_not_describe_the_mock_export(observed, cases):
    _, paths = observed
    for index, case in enumerate(cases, 1):
        case["test_id"] = f"TC_{index:03d}"
    write_json(paths[1], {"schema_version": "1.0", "tests": cases})
    assert audit_generation(*paths)["valid"] is False


def test_new_report_hashes_detect_modified_content(tmp_path):
    output = tmp_path / "custom_filename.json"
    result = TestGenerator(MockLLMClient()).generate(SPEC, output)
    paths = (SPEC, output, result.report_path, result.hypotheses_path)
    assert audit_generation(*paths)["valid"] is True
    assert not audit_generation(*paths)["warnings"]
    output.write_bytes(output.read_bytes() + b"\n")
    audit = audit_generation(*paths)
    assert audit["valid"] is False
    assert any(x["check"] == "tests_artifact_hash" and not x["passed"] for x in audit["checks"])


def test_report_hash_paths_support_separate_directories(tmp_path):
    result = TestGenerator(MockLLMClient()).generate(
        SPEC, tmp_path / "tests" / "cases.json", report_path=tmp_path / "reports" / "generation.json",
        hypotheses_path=tmp_path / "hypotheses" / "uncertain.json")
    audit = audit_generation(SPEC, tmp_path / "tests" / "cases.json", result.report_path, result.hypotheses_path)
    assert audit["valid"] is True


def test_audit_cli_exit_codes_and_input_protection(observed, capsys):
    data, paths = observed
    args = ["audit", "--spec", str(paths[0]), "--tests", str(paths[1]),
            "--generation-report", str(paths[2]), "--hypotheses", str(paths[3])]
    assert main(args) == 0
    assert main([*args, "--output", str(paths[1])]) == 2
    data["report"]["metrics"]["validated_tests"] = 5
    write_json(paths[2], data["report"])
    assert main(args) == 1
    capsys.readouterr()
