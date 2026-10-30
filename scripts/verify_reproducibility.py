"""Verify both recorded datasets twice without network; save a concise audit."""

import hashlib
import platform
import tempfile
from importlib.metadata import version
from pathlib import Path

from ai_generator.exporter import write_json
from ai_generator.llm_client import MockLLMClient
from ai_generator.test_generator import TestGenerator
from ai_generator.validator import SemanticValidator, validate_contract
from ai_generator.openapi_parser import OpenAPIParser


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    spec_path = root / "examples" / "sample_openapi.json"
    validator = SemanticValidator(OpenAPIParser().parse(spec_path))
    datasets = []
    with tempfile.TemporaryDirectory(prefix="s5-replay-") as directory:
        for filename in ("products_recording.json", "products_recording_b.json"):
            fixture = root / "ai_generator" / "fixtures" / filename
            contents = []
            for run in (1, 2):
                output = Path(directory) / fixture.stem / str(run) / "generated_tests.json"
                result = TestGenerator(MockLLMClient(fixture)).generate(spec_path, output)
                suite = validate_contract(output.read_text(encoding="utf-8"))
                if not suite.tests or any(validator.validate(case).outcome != "accepted" for case in suite.tests):
                    raise RuntimeError("Recorded output failed validation")
                contents.append(output.read_bytes())
            if contents[0] != contents[1]:
                raise RuntimeError("Recorded output is not reproducible")
            datasets.append({"fixture": filename, "runs": 2, "byte_identical_tests": True,
                             "contract_valid": True, "semantic_valid": True,
                             "tests_sha256": hashlib.sha256(contents[0]).hexdigest(),
                             "metrics": {key: value for key, value in result.report["metrics"].items()
                                         if key != "generation_seconds"}})
    report = {"mode": "mock", "live_provider_called": False, "python": platform.python_version(),
              "dependencies": {name: version(name) for name in ("pydantic", "PyYAML", "httpx", "python-dotenv", "jsonschema", "pytest")},
              "scope": "Test exports compared byte for byte; report timings/log timestamps are intentionally excluded",
              "datasets": datasets}
    destination = root / "outputs" / "reproducibility_report.json"
    write_json(destination, report)
    print(f"Verified 2 recorded datasets, 2 runs each: {destination}")


if __name__ == "__main__":
    main()
