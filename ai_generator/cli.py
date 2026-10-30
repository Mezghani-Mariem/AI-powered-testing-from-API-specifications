"""Run with python -m ai_generator.cli. No target API calls are made."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from .audit import audit_generation
from .config import LLMConfig
from .errors import GeneratorError
from .exporter import write_json
from .llm_client import LiveLLMClient, MockLLMClient
from .openapi_parser import OpenAPIParser
from .prompt_logger import PromptLogger
from .test_generator import TestGenerator
from .validator import SemanticValidator, validate_contract


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="S5 / Mariem: OpenAPI -> AI test JSON (no API execution)")
    commands = root.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Generate and validate test data")
    generate.add_argument("--spec", required=True, type=Path)
    generate.add_argument("--output", required=True, type=Path)
    generate.add_argument("--mode", choices=["mock", "live"], required=True)
    generate.add_argument("--tests-per-operation", type=int, default=3)
    generate.add_argument("--env-file", type=Path, default=Path(".env"))
    generate.add_argument("--mock-fixture", type=Path)
    generate.add_argument("--report", type=Path)
    generate.add_argument("--hypotheses", type=Path)
    generate.add_argument("--log-prompts", action="store_true", help="Write metadata/validation trace")
    generate.add_argument("--log-content", action="store_true", help="Also log sensitive prompt/response content (opt-in)")
    generate.add_argument("--log-path", type=Path, default=Path("outputs/prompt_logs/prompts.jsonl"))
    validate = commands.add_parser("validate", help="Validate contract, optionally semantics")
    validate.add_argument("--tests", required=True, type=Path)
    validate.add_argument("--spec", type=Path)
    validate.add_argument("--report", type=Path)
    inspect = commands.add_parser("inspect", help="Inspect normalized OpenAPI operations")
    inspect.add_argument("--spec", required=True, type=Path)
    audit = commands.add_parser("audit", help="Check tests and generation/hypotheses reports together, offline")
    audit.add_argument("--spec", required=True, type=Path)
    audit.add_argument("--tests", required=True, type=Path)
    audit.add_argument("--generation-report", required=True, type=Path)
    audit.add_argument("--hypotheses", required=True, type=Path)
    audit.add_argument("--output", type=Path)
    return root


def main(argv: list[str] | None = None) -> int:
    root = parser()
    args = root.parse_args(argv)
    try:
        if args.command == "audit":
            inputs = (args.spec, args.tests, args.generation_report, args.hypotheses)
            if args.output and args.output.resolve() in {path.resolve() for path in inputs}:
                raise ValueError("Audit output must not overwrite an input")
            result = audit_generation(*inputs)
            if args.output:
                write_json(args.output, result)
            print(json.dumps(result, indent=2))
            return 0 if result["valid"] else 1
        if args.command == "inspect":
            spec = OpenAPIParser().parse(args.spec)
            print(json.dumps({"spec_sha256": spec.sha256, "operations": [op.key for op in spec.operations], "warnings": spec.warnings}, indent=2))
            return 0
        if args.command == "validate":
            suite = validate_contract(args.tests.read_text(encoding="utf-8"))
            details = []
            if args.spec:
                validator = SemanticValidator(OpenAPIParser().parse(args.spec))
                for case in suite.tests:
                    result = validator.validate(case)
                    details.append({"test_id": case.test_id, "outcome": result.outcome, "reasons": result.reasons})
            valid = all(item["outcome"] == "accepted" for item in details)
            report = {"contract_valid": True, "semantic_checked": bool(args.spec), "tests": len(suite.tests), "valid": valid, "details": details}
            if args.report:
                forbidden = {args.tests.resolve()}
                if args.spec:
                    forbidden.add(args.spec.resolve())
                if args.report.resolve() in forbidden:
                    raise ValueError("Validation report must not overwrite the input tests/spec")
                write_json(args.report, report)
            print(json.dumps(report, indent=2))
            return 0 if valid else 1
        if args.log_content and not args.log_prompts:
            raise ValueError("--log-content requires --log-prompts")
        if args.mode == "live" and args.mock_fixture:
            raise ValueError("--mock-fixture is only available in mock mode")
        config = LLMConfig.from_env(args.env_file) if args.mode == "live" else LLMConfig()
        client = LiveLLMClient(config) if args.mode == "live" else MockLLMClient(args.mock_fixture)
        if args.log_prompts:
            protected = {args.spec.resolve(), args.output.resolve(), args.env_file.resolve()}
            protected.update(Path(p).resolve() for p in (args.report or args.output.parent / "generation_report.json", args.hypotheses or args.output.parent / "hypothetical_scenarios.json"))
            if args.log_path.resolve() in protected:
                raise ValueError("Log path must be distinct from input, output and configuration files")
        logger = PromptLogger(args.log_path if args.log_prompts else None, log_content=args.log_content,
                              secrets=(config.api_key.get_secret_value(),))
        result = TestGenerator(client, logger=logger, settings=config.public_settings()).generate(
            args.spec, args.output, tests_per_operation=args.tests_per_operation,
            report_path=args.report, hypotheses_path=args.hypotheses)
        print(json.dumps({"mode": client.mode, "status": result.report["status"], "tests": len(result.suite.tests),
                          "output": str(args.output), "report": str(result.report_path), "hypotheses": str(result.hypotheses_path)}, indent=2))
        return 1 if result.report["operation_failures"] else 0
    except ValidationError:
        # Pydantic configuration errors may contain the API key as an input value.
        message = "invalid test/hypothesis contract" if args.command in {"validate", "audit"} else "invalid LLM configuration; check .env field types, bounds and provider URL"
        print(f"Error: {message}", file=sys.stderr)
        return 2
    except (GeneratorError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
