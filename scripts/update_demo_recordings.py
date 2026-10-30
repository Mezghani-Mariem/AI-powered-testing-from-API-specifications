"""Refresh HAND-AUTHORED mock snapshots from curator-authored demo scenarios.

No model is called. This maintenance script is not used during generation.
Run from repository root: python -m scripts.update_demo_recordings
"""

from pathlib import Path

from ai_generator.exporter import write_json
from ai_generator.openapi_parser import OpenAPIParser


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    spec = OpenAPIParser().parse(root / "examples" / "sample_openapi.json")
    for alternate, filename in ((False, "products_recording.json"), (True, "products_recording_b.json")):
        operations = {}
        for operation in spec.operations:
            tests = []
            scenarios = list(reversed(operation.scenarios)) if alternate else operation.scenarios
            for index, scenario in enumerate(scenarios, 1):
                request = scenario["request"]
                tests.append({
                    "test_id": f"recorded_{index}", "name": scenario["name"],
                    "method": operation.method, "endpoint": operation.endpoint,
                    "test_type": scenario["test_type"], "path_params": request.get("path_params", {}),
                    "query_params": request.get("query_params", {}), "headers": request.get("headers", {}),
                    "body": request.get("body"), "expected_status": scenario["expected_status"],
                    "expected_body": scenario.get("expected_body"),
                })
            operations[operation.key] = {"operation": operation.prompt_data(), "tests": tests}
        write_json(root / "ai_generator" / "fixtures" / filename, {
            "recording_version": "1.0", "model": "mock-hand-authored-products-v1" + ("-b" if alternate else ""),
            "provenance": "Hand-authored fixture playback; no LLM generated these responses",
            "operations": operations,
        })


if __name__ == "__main__":
    main()
