"""Parse -> prompt -> LLM/playback -> validate -> deduplicate -> export -> metrics."""

import hashlib
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from .errors import LLMError
from .exporter import export_suite, write_json
from .json_utils import canonical
from .llm_client import LLMResult
from .metrics import GenerationMetrics
from .openapi_parser import OpenAPIParser, Operation, ParsedSpec
from .prompt_builder import PROMPT_VERSION, build_messages
from .prompt_logger import PromptLogger
from .schemas import TestCase, TestSuite
from .validator import SemanticValidator


class GenerationClient(Protocol):
    model: str
    mode: str
    attempts: int

    def generate(self, messages: list[dict[str, str]], operation: Operation,
                 spec: ParsedSpec, target: int) -> LLMResult: ...


@dataclass
class GenerationOutput:
    suite: TestSuite
    report: dict
    report_path: Path
    hypotheses_path: Path


class TestGenerator:
    __test__ = False

    def __init__(self, client: GenerationClient, *, logger: PromptLogger | None = None,
                 settings: dict | None = None):
        self.client = client
        self.logger = logger or PromptLogger()
        self.settings = settings or {}

    def generate(self, spec_path: str | Path, output: str | Path, *, tests_per_operation: int = 3,
                 report_path: str | Path | None = None,
                 hypotheses_path: str | Path | None = None) -> GenerationOutput:
        if not 1 <= tests_per_operation <= 50:
            raise ValueError("tests_per_operation must be between 1 and 50")
        output = Path(output)
        report_path = Path(report_path) if report_path else output.parent / "generation_report.json"
        hypotheses_path = Path(hypotheses_path) if hypotheses_path else output.parent / "hypothetical_scenarios.json"
        paths = [Path(p).resolve() for p in (spec_path, output, report_path, hypotheses_path)]
        if len(set(paths)) != len(paths):
            raise ValueError("Spec, test export, report and hypotheses paths must be distinct")
        start = time.perf_counter()
        spec = OpenAPIParser().parse(spec_path)
        validator = SemanticValidator(spec)
        metrics = GenerationMetrics(len(spec.operations))
        rejected: list[dict] = []
        hypotheses: list[dict] = []
        failures: list[dict] = []
        seen: set[str] = set()
        for operation in spec.operations:
            messages = build_messages(operation, tests_per_operation)
            before_attempts = self.client.attempts
            raw: str | None = None
            error: str | None = None
            results: list[dict] = []
            op_start = time.perf_counter()
            try:
                response = self.client.generate(messages, operation, spec, tests_per_operation)
                raw = response.raw
                if self.client.mode == "mock":
                    metrics.mock_playbacks += 1
                for index, item in enumerate(response.data["tests"]):
                    metrics.proposed_tests += 1
                    try:
                        case = TestCase.model_validate(item)
                    except ValidationError as exc:
                        metrics.structurally_rejected_tests += 1
                        # Do not include Pydantic's input values (possibly sensitive).
                        reasons = [{"location": list(e["loc"]), "type": e["type"]} for e in exc.errors(include_input=False, include_url=False)]
                        detail = {"operation": operation.key, "candidate_index": index, "stage": "structure", "errors": reasons}
                        rejected.append(detail)
                        results.append({"candidate_index": index, "outcome": "rejected", "stage": "structure"})
                        continue
                    metrics.structurally_valid_tests += 1
                    validation = validator.validate(case, operation=operation)
                    detail = {"operation": operation.key, "candidate_index": index,
                              "outcome": validation.outcome, "reasons": validation.reasons,
                              "request_violations": validation.request_violations}
                    results.append(detail)
                    if validation.outcome == "hypothetical":
                        metrics.hypothetical_tests += 1
                        hypotheses.append({**detail, "candidate": case.model_dump(mode="json")})
                    elif validation.outcome == "rejected":
                        metrics.semantically_rejected_tests += 1
                        rejected.append(detail)
                    else:
                        metrics.semantically_accepted_tests += 1
                        # IDs and names are labels, not request/assertion behavior.
                        fingerprint = canonical(case.model_dump(exclude={"test_id", "name"}))
                        if fingerprint in seen:
                            metrics.duplicates += 1
                            detail["duplicate"] = True
                            continue
                        seen.add(fingerprint)
                        metrics.tests.append(case.model_copy(update={"test_id": f"TC_{len(metrics.tests) + 1:03d}"}))
            except LLMError as exc:
                error = str(exc)
                raw = exc.raw_response
                metrics.llm_failures += 1
                failures.append({"operation": operation.key, "error": error})
            finally:
                attempts = self.client.attempts - before_attempts
                metrics.llm_attempts += attempts
                self.logger.record(model=self.client.model, mode=self.client.mode, settings=self.settings,
                                   spec_hash=spec.sha256, operation=operation.key, messages=messages,
                                   raw_response=raw, validation=results, error=error, attempts=attempts,
                                   duration_seconds=time.perf_counter() - op_start)
        suite = TestSuite(schema_version="1.0", tests=metrics.tests)
        metrics.generation_seconds = time.perf_counter() - start
        report = {
            "report_version": "1.0", "mode": self.client.mode, "model": self.client.model,
            "prompt_version": PROMPT_VERSION, "spec_sha256": spec.sha256,
            "status": "partial_error" if failures else "completed",
            "tests_per_operation_target": tests_per_operation,
            "target_policy": "soft maximum requested in prompts; provider excess is still validated and counted",
            "metrics": metrics.report(), "parser_warnings": spec.warnings,
            "rejections": rejected, "operation_failures": failures,
            "assurance": "specification evidence only; API availability, state and actual behavior were not verified",
        }
        export_suite(suite, output)
        write_json(hypotheses_path, {"report_version": "1.0", "mode": self.client.mode,
                                     "executable": False, "scenarios": hypotheses})
        # Report metadata binds these files even when a custom test filename is used.
        # Nothing is added to the integration contract itself.
        report["artifacts"] = {
            label: {"path": Path(os.path.relpath(path.resolve(), report_path.parent.resolve())).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for label, path in (("tests", output), ("hypotheses", hypotheses_path))
        }
        write_json(report_path, report)
        return GenerationOutput(suite, report, report_path, hypotheses_path)
