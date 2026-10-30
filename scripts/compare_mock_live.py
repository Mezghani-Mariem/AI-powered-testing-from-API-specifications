"""Audit the preserved S5 experiment and replay mock separately, without any LLM call.

Original live/mock files and measurements are never overwritten. Output is confined
to outputs/consolidation. The user-provided legacy live report has no artifact hashes.
"""

import hashlib
from pathlib import Path

from ai_generator.audit import audit_generation
from ai_generator.exporter import write_json
from ai_generator.json_utils import canonical, loads_json
from ai_generator.llm_client import MockLLMClient
from ai_generator.test_generator import TestGenerator
from ai_generator.validator import SemanticValidator, validate_contract
from ai_generator.openapi_parser import OpenAPIParser


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    spec = root / "examples" / "sample_openapi.json"
    source = root / "outputs"
    destination = source / "consolidation"
    original_paths = [spec, source / "generated_tests.json", source / "generated_tests_ollama.json",
                      source / "generation_report.json", source / "hypothetical_scenarios.json",
                      source / "reproducibility_report.json", source / "validation_report.json",
                      *(source / "demo_set_b" / name for name in ("generated_tests.json", "generation_report.json", "hypothetical_scenarios.json"))]
    before = {path: path.read_bytes() for path in original_paths}
    live = audit_generation(spec, source / "generated_tests_ollama.json", source / "generation_report.json", source / "hypothetical_scenarios.json")
    if not live["valid"]:
        raise RuntimeError("Preserved live artifacts are inconsistent; inspect audit before comparing")
    replay_path = destination / "mock_replay" / "generated_tests.json"
    replay = TestGenerator(MockLLMClient()).generate(spec, replay_path)
    mock = audit_generation(spec, replay_path, replay.report_path, replay.hypotheses_path)
    if not mock["valid"] or replay_path.read_bytes() != before[source / "generated_tests.json"]:
        raise RuntimeError("Mock replay differs from the preserved mock baseline")
    historical_repro = loads_json(before[source / "reproducibility_report.json"].decode("utf-8"))
    historical_mock = next(row for row in historical_repro["datasets"] if row["fixture"] == "products_recording.json")
    mock_hash = hashlib.sha256(before[source / "generated_tests.json"]).hexdigest()
    if historical_mock["tests_sha256"] != mock_hash:
        raise RuntimeError("Historical reproducibility report does not match the preserved mock export")
    mock_suite = validate_contract(before[source / "generated_tests.json"].decode("utf-8"))
    live_suite = validate_contract(before[source / "generated_tests_ollama.json"].decode("utf-8"))
    validator = SemanticValidator(OpenAPIParser().parse(spec))
    if any(validator.validate(case).outcome != "accepted" for case in mock_suite.tests):
        raise RuntimeError("Preserved mock export failed semantic revalidation")
    def behavior(case):
        return canonical(case.model_dump(exclude={"test_id", "name"}))
    overlap = set(map(behavior, mock_suite.tests)) & set(map(behavior, live_suite.tests))
    live_report = loads_json(before[source / "generation_report.json"].decode("utf-8"))
    comparison = {
        "comparison_version": "1.0", "target_api_executed": False, "new_llm_call_performed": False,
        "original_files_unchanged": True,
        "sources": {path.relative_to(root).as_posix(): hashlib.sha256(value).hexdigest() for path, value in before.items()},
        "mock": {"tests_file": "outputs/generated_tests.json", "source_prompt_version": "1.0.0",
                 "metrics": historical_mock["metrics"], "original_generation_seconds": None,
                 "timing_note": "Original matching generation report was replaced by the live run; historical reproducibility metrics exclude time. New replay time is not a model latency comparison.",
                 "replay_byte_identical": True, "replay_prompt_version": replay.report["prompt_version"],
                 "experimental_value": "Hand-authored deterministic fixtures: pipeline regression, not a model generation experiment."},
        "live": {"tests_file": "outputs/generated_tests_ollama.json", "model": live_report["model"],
                 "source_prompt_version": live_report["prompt_version"], "metrics": live_report["metrics"],
                 "experimental_value": "One user-reported Ollama model run supported by persisted output artifacts; audited offline, without independent runtime verification or API execution."},
        "identical_exported_behaviors": len(overlap),
        "not_exported_live": [{"mock_test_id": case.test_id, "operation": f"{case.method} {case.endpoint}",
                               "test_type": case.test_type} for case in mock_suite.tests if behavior(case) not in overlap],
        "prompt_improvement": {"new_version": replay.report["prompt_version"], "new_live_experiment_performed": False,
                               "effect_on_model_acceptance": "unmeasured; historical 4/6 result is unchanged"},
        "limits": ["Single run on two operations is not a general benchmark.",
                   "100% operation coverage does not imply a positive test for each operation or behavior coverage.",
                   "Legacy source reports lack historical output hashes; explicit file association was checked semantically and arithmetically."],
    }
    if any(path.read_bytes() != value for path, value in before.items()):
        raise RuntimeError("A source artifact changed during audit")
    write_json(destination / "live_audit.json", live)
    write_json(destination / "mock_audit.json", mock)
    write_json(destination / "comparison.json", comparison)
    print(f"Audit passed: mock {len(mock_suite.tests)}, live {len(live_suite.tests)}, overlap {len(overlap)}. Original artifacts unchanged.")
    print(f"Comparison: {destination / 'comparison.json'}")


if __name__ == "__main__":
    main()
