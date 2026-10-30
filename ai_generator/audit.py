"""Read-only consistency audit of a test export and its two generation reports."""

import hashlib
import math
from collections import Counter
from pathlib import Path

from .errors import OutputError
from .json_utils import canonical, loads_json
from .openapi_parser import OpenAPIParser
from .schemas import TestCase
from .validator import SemanticValidator, validate_contract


def audit_generation(spec_path: str | Path, tests_path: str | Path,
                     report_path: str | Path, hypotheses_path: str | Path) -> dict:
    paths = {"spec": Path(spec_path), "tests": Path(tests_path),
             "generation_report": Path(report_path), "hypotheses": Path(hypotheses_path)}
    spec = OpenAPIParser().parse(paths["spec"])
    suite = validate_contract(paths["tests"].read_text(encoding="utf-8"))
    report = loads_json(paths["generation_report"].read_text(encoding="utf-8"))
    hypotheses = loads_json(paths["hypotheses"].read_text(encoding="utf-8"))
    if not isinstance(report, dict) or not isinstance(report.get("metrics"), dict):
        raise OutputError("Generation report needs a metrics object")
    if not isinstance(hypotheses, dict) or not isinstance(hypotheses.get("scenarios"), list):
        raise OutputError("Hypotheses report needs a scenarios array")
    metrics = report["metrics"]
    checks: list[dict] = []
    warnings: list[str] = []

    def check(name: str, condition: bool) -> None:
        checks.append({"check": name, "passed": bool(condition)})

    validator = SemanticValidator(spec)
    exported = []
    fingerprints = []
    for case in suite.tests:
        result = validator.validate(case)
        exported.append({"test_id": case.test_id, "operation": f"{case.method} {case.endpoint}",
                         "outcome": result.outcome, "reasons": result.reasons,
                         "request_violations": result.request_violations})
        fingerprints.append(canonical(case.model_dump(exclude={"test_id", "name"})))
    check("all_exported_tests_semantically_accepted", all(x["outcome"] == "accepted" for x in exported))
    check("no_exported_behavior_duplicates", len(fingerprints) == len(set(fingerprints)))
    hypothetical_results = []
    locations = []
    for item in hypotheses["scenarios"]:
        if not isinstance(item, dict) or not isinstance(item.get("candidate"), dict):
            raise OutputError("Each hypothesis needs a candidate object")
        case = TestCase.model_validate(item["candidate"])
        result = validator.validate(case)
        operation = f"{case.method} {case.endpoint}"
        index = item.get("candidate_index")
        check("hypothesis_location_is_valid", item.get("operation") == operation and type(index) is int and index >= 0)
        check("hypothesis_stays_hypothetical", result.outcome == item.get("outcome") == "hypothetical")
        check("hypothesis_reasons_match", result.reasons == item.get("reasons"))
        check("hypothesis_violations_match", result.request_violations == item.get("request_violations"))
        check("hypothesis_not_in_export", canonical(case.model_dump(exclude={"test_id", "name"})) not in fingerprints)
        locations.append((item.get("operation"), index))
        hypothetical_results.append({"operation": operation, "candidate_index": index,
                                     "source_test_id": case.test_id, "outcome": result.outcome,
                                     "reasons": result.reasons, "request_violations": result.request_violations})
    check("unique_hypothesis_locations", len(locations) == len(set(locations)))
    check("spec_hash_matches", report.get("spec_sha256") == spec.sha256)
    check("modes_match", report.get("mode") in {"mock", "live"} and hypotheses.get("mode") == report.get("mode"))
    check("hypotheses_are_non_executable", hypotheses.get("executable") is False)
    count_fields = ("operations_analyzed", "proposed_tests", "structurally_valid_tests", "structurally_rejected_tests",
                    "semantically_accepted_tests_before_deduplication", "semantically_rejected_tests",
                    "hypothetical_tests", "validated_tests", "rejected_tests", "duplicates", "operations_covered",
                    "llm_attempts", "llm_failures", "mock_playbacks")
    counts_valid = all(type(metrics.get(key)) is int and metrics[key] >= 0 for key in count_fields)
    check("nonnegative_integer_counts", counts_valid)
    check("analyzed_operations_match", metrics.get("operations_analyzed") == len(spec.operations))
    check("export_count_matches", metrics.get("validated_tests") == len(suite.tests))
    check("hypothesis_count_matches", metrics.get("hypothetical_tests") == len(hypothetical_results))
    categories = {key: Counter(case.test_type for case in suite.tests)[key] for key in ("positive", "negative", "boundary")}
    covered = len({(case.method, case.endpoint) for case in suite.tests})
    check("categories_match", metrics.get("category_distribution") == categories)
    check("covered_operations_match", metrics.get("operations_covered") == covered)
    if counts_valid:
        m = metrics
        accepted = m["semantically_accepted_tests_before_deduplication"]
        check("proposed_equals_structural_partition", m["proposed_tests"] == m["structurally_valid_tests"] + m["structurally_rejected_tests"])
        check("structural_equals_semantic_partition", m["structurally_valid_tests"] == accepted + m["semantically_rejected_tests"] + m["hypothetical_tests"])
        check("accepted_equals_exported_plus_duplicates", accepted == len(suite.tests) + m["duplicates"])
        check("rejected_partition_matches", m["rejected_tests"] == m["structurally_rejected_tests"] + m["semantically_rejected_tests"] + m["hypothetical_tests"])
        check("proposed_equals_exported_rejected_duplicates", m["proposed_tests"] == len(suite.tests) + m["rejected_tests"] + m["duplicates"])
        for field, numerator, denominator in (
            ("structural_validity_percent", m["structurally_valid_tests"], m["proposed_tests"]),
            ("semantic_acceptance_percent", accepted, m["structurally_valid_tests"]),
            ("operation_generation_coverage_percent", covered, len(spec.operations)),
        ):
            expected = round(100 * numerator / denominator, 4) if denominator else None
            value = metrics.get(field)
            check(field + "_matches", value is None if expected is None else type(value) in (int, float) and abs(value - expected) < 0.0001)
        check("mock_has_no_llm_attempts", report.get("mode") != "mock" or m["llm_attempts"] == 0)
        check("live_has_no_mock_playbacks", report.get("mode") != "live" or m["mock_playbacks"] == 0)
        rejections = report.get("rejections", [])
        failures = report.get("operation_failures", [])
        if not isinstance(rejections, list) or not isinstance(failures, list) or any(not isinstance(x, dict) for x in rejections):
            raise OutputError("Report rejections/failures must be arrays of records")
        check("structural_rejection_records_match", sum(x.get("stage") == "structure" for x in rejections) == m["structurally_rejected_tests"])
        check("semantic_rejection_records_match", sum(x.get("outcome") == "rejected" for x in rejections) == m["semantically_rejected_tests"])
        check("failure_records_match", len(failures) == m["llm_failures"])
        check("status_matches_failures", report.get("status") == ("partial_error" if failures else "completed"))
    seconds = metrics.get("generation_seconds")
    check("generation_time_is_finite_nonnegative", type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0)
    artifacts = report.get("artifacts")
    if artifacts is None:
        warnings.append("Legacy report has no output file hashes; the association relies on explicit input paths and consistency checks, not a historical cryptographic binding.")
    elif not isinstance(artifacts, dict):
        raise OutputError("Report artifacts must be an object")
    else:
        for name in ("tests", "hypotheses"):
            artifact = artifacts.get(name, {})
            if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
                check(name + "_artifact_binding", False)
                continue
            # Resolve for comparison only: never read a path supplied by the report.
            check(name + "_artifact_path", (paths["generation_report"].parent / artifact["path"]).resolve() == paths[name].resolve())
            check(name + "_artifact_hash", artifact.get("sha256") == hashlib.sha256(paths[name].read_bytes()).hexdigest())
    return {
        "audit_version": "1.0", "valid": all(item["passed"] for item in checks),
        "mode": report.get("mode"), "model": report.get("model"), "source_prompt_version": report.get("prompt_version"),
        "sources": {name: {"path": path.as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for name, path in paths.items()},
        "checks": checks, "warnings": warnings, "exported_tests": exported,
        "hypothetical_scenarios": hypothetical_results,
        "scope": "Persisted artifact consistency and specification evidence only; no LLM call or target API execution, and no independent proof of a live provider call.",
    }
