"""Run one real local Ollama experiment, preserving all previous output files.

Run from the repository root: python -m scripts.evaluate_prompt_versions
Every invocation creates a new directory. No mock fallback or source-file updates.
The historical 1.0.0 report does not record its LLM settings; this limitation is saved.
"""

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

import httpx

from ai_generator.config import LLMConfig
from ai_generator.exporter import write_json
from ai_generator.json_utils import loads_json
from ai_generator.prompt_builder import PROMPT_VERSION


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_command(argv: list[str], cwd: Path, log_path: Path) -> int:
    process = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    log_path.write_text(process.stdout + process.stderr, encoding="utf-8")
    return process.returncode


def summarize_experiment(run_dir: Path) -> dict:
    """Summarize saved observations only; this function performs no inference."""
    root = Path(__file__).resolve().parents[1]
    metadata = loads_json((run_dir / "experiment_metadata.json").read_text(encoding="utf-8"))
    old_dir, new_dir = run_dir / "historical_prompt_1_0", run_dir / "prompt_1_1"
    reports = {name: loads_json((folder / "generation_report.json").read_text(encoding="utf-8"))
               for name, folder in (("1.0.0", old_dir), ("1.1.0", new_dir))}
    audits = {name: loads_json((folder / "audit.json").read_text(encoding="utf-8"))
              for name, folder in (("1.0.0", old_dir), ("1.1.0", new_dir))}
    if not all(audit["valid"] for audit in audits.values()):
        raise RuntimeError("Cannot compare results that failed audit")
    fields = ("proposed_tests", "validated_tests", "hypothetical_tests", "structural_validity_percent",
              "semantic_acceptance_percent", "operation_generation_coverage_percent", "operations_covered",
              "operations_analyzed", "generation_seconds", "duplicates", "llm_attempts")
    metrics = {field: {"1.0.0": reports["1.0.0"]["metrics"][field], "1.1.0": reports["1.1.0"]["metrics"][field]}
               for field in fields}
    for values in metrics.values():
        values["delta_1_1_minus_1_0"] = round(values["1.1.0"] - values["1.0.0"], 6)
    events = [loads_json(line) for line in (new_dir / "prompts.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(events) != reports["1.1.0"]["metrics"]["operations_analyzed"]:
        raise RuntimeError("Unexpected number of logged live operation events")
    if any(event["mode"] != "live" or event["prompt_version"] != "1.1.0" or
           event["llm_parameters"] != metadata["effective_llm_parameters"] for event in events):
        raise RuntimeError("Actual logged configuration differs from experiment metadata")
    suites = {name: loads_json((folder / "generated_tests.json").read_text(encoding="utf-8"))["tests"]
              for name, folder in (("1.0.0", old_dir), ("1.1.0", new_dir))}
    positives = {name: [case for case in cases if case["method"] == "GET" and case["test_type"] == "positive"]
                 for name, cases in suites.items()}
    raw_get_positives = [case for event in events if event["operation"].startswith("GET ")
                         for case in loads_json(event["response"])["tests"] if case["test_type"] == "positive"]
    changed = [path for path, digest in metadata["preserved_files_before_run"].items()
               if not (root / path).is_file() or sha256(root / path) != digest]
    if changed:
        raise RuntimeError("Historical artifacts changed: " + ", ".join(changed))
    junit_path = run_dir / "pytest_results.xml"
    pytest_results = None
    if junit_path.exists():
        suites_xml = list(ElementTree.parse(junit_path).getroot().iter("testsuite"))
        pytest_results = {key: sum(int(suite.get(key, "0")) for suite in suites_xml)
                          for key in ("tests", "failures", "errors", "skipped")}
    summary = {
        "comparison_version": "1.0", "observed_live_runs_per_version": 1,
        "spec_sha256": reports["1.1.0"]["spec_sha256"],
        "same_spec_verified": reports["1.0.0"]["spec_sha256"] == reports["1.1.0"]["spec_sha256"],
        "same_model_name_verified": reports["1.0.0"]["model"] == reports["1.1.0"]["model"],
        "historical_llm_settings_equality_verified": False,
        "current_llm_settings_verified_in_logs": True,
        "effective_llm_parameters": metadata["effective_llm_parameters"],
        "metrics": metrics,
        "category_distribution": {name: report["metrics"]["category_distribution"] for name, report in reports.items()},
        "get_positive_exported": {name: len(cases) for name, cases in positives.items()},
        "new_get_positive_cases": positives["1.1.0"], "new_raw_get_positive_cases": raw_get_positives,
        "audits_valid": {name: audit["valid"] for name, audit in audits.items()},
        "all_historical_outputs_unchanged": not changed,
        "historical_copies_byte_identical": all(sha256(root / item["copy"]) == item["sha256"] for item in metadata["historical_archive"].values()),
        "new_calls_logged": [{"operation": event["operation"], "attempts": event["attempts"],
                              "duration_seconds": event["duration_seconds"], "mode": event["mode"]} for event in events],
        "pytest_results": pytest_results,
        "interpretation": "More tests accepted and documented GET assertions retained in this observation; generation was slower. One run per version, unrecorded old LLM settings and unknown old load state prevent general or isolated causal claims.",
        "new_model_initially_loaded": any(item.get("name") == metadata["effective_llm_parameters"]["model"]
                                          for item in metadata["models_loaded_before_run"]["models"]),
        "target_api_executed": False,
    }
    write_json(run_dir / "comparison.json", summary)
    return summary


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    outputs = root / "outputs"
    spec_path = root / "examples" / "sample_openapi.json"
    history = {
        "generated_tests.json": outputs / "generated_tests_ollama.json",
        "generation_report.json": outputs / "generation_report.json",
        "hypothetical_scenarios.json": outputs / "hypothetical_scenarios.json",
        "sample_openapi.json": spec_path,
    }
    old = loads_json(history["generation_report.json"].read_text(encoding="utf-8"))
    if old["prompt_version"] != "1.0.0" or PROMPT_VERSION != "1.1.0":
        raise RuntimeError("This experiment expects historical prompt 1.0.0 and current prompt 1.1.0")
    if old["spec_sha256"] != sha256(spec_path):
        raise RuntimeError("OpenAPI differs from the historical experiment")
    config = LLMConfig.from_env(root / ".env")
    url = urlsplit(config.base_url)
    if url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("This experiment is restricted to local Ollama")
    if config.model != old["model"] or config.model != "qwen2.5-coder:7b":
        raise RuntimeError("Configured model differs from the historical experiment")
    server_url = url.scheme + "://" + url.netloc
    with httpx.Client(timeout=10, trust_env=False) as client:
        server = client.get(server_url + "/api/version")
        server.raise_for_status()
        tags = client.get(server_url + "/api/tags")
        tags.raise_for_status()
        model = next((item for item in tags.json()["models"] if item["name"] == config.model), None)
        if model is None:
            raise RuntimeError("Configured model is not installed in Ollama")
        loaded = client.get(server_url + "/api/ps")
        loaded.raise_for_status()

    # Capture existing outputs before allocating the new experiment directory.
    preserved = {path: sha256(path) for path in outputs.rglob("*") if path.is_file()}
    preserved[spec_path] = sha256(spec_path)
    parent = outputs / "experiments"
    parent.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="ollama_prompt_1_1_20261030_", dir=parent))
    archive = run_dir / "historical_prompt_1_0"
    archive.mkdir()
    for name, path in history.items():
        shutil.copy2(path, archive / name)
    new_dir = run_dir / "prompt_1_1"
    new_dir.mkdir()
    relative = lambda path: path.relative_to(root).as_posix()
    public_config = config.public_settings()
    metadata = {
        "experiment_version": "1.0", "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "timezone_for_reporting": "Africa/Lagos", "mode": "live", "new_live_runs": 1,
        "source_spec": relative(spec_path), "spec_sha256": sha256(spec_path),
        "source_prompt_version": PROMPT_VERSION, "base_url": config.base_url,
        "effective_llm_parameters": public_config,
        "historical_llm_parameters_recorded": False,
        "parameter_comparability": "Current .env configuration was used unchanged, with no CLI override. The historical report and available logs do not record the old live settings; exact equality cannot be verified.",
        "ollama_version": server.json(), "installed_model": model,
        "models_loaded_before_run": loaded.json(),
        "python": platform.python_version(), "platform": platform.platform(),
        "historical_archive": {name: {"source": relative(path), "copy": relative(archive / name), "sha256": sha256(path)} for name, path in history.items()},
        "preserved_files_before_run": {relative(path): digest for path, digest in preserved.items()},
        "scope": "One exploratory live run per prompt version, no target API execution; no general improvement claim.",
    }
    write_json(run_dir / "experiment_metadata.json", metadata)
    print(f"Experiment: {relative(run_dir)}", flush=True)
    print("Historical artifacts archived. Starting real Ollama generation with prompt 1.1.0.", flush=True)

    generate = [sys.executable, "-m", "ai_generator.cli", "generate", "--spec", relative(spec_path),
                "--output", relative(new_dir / "generated_tests.json"), "--mode", "live",
                "--tests-per-operation", str(old["tests_per_operation_target"]),
                "--env-file", ".env", "--log-prompts", "--log-content",
                "--log-path", relative(new_dir / "prompts.jsonl")]
    metadata["generation_command"] = generate
    metadata["generation_exit_code"] = run_command(generate, root, new_dir / "generation_command.log")
    metadata["generation_finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    print(f"Generation completed with exit code {metadata['generation_exit_code']}.", flush=True)

    metadata["audit_exit_codes"] = {}
    for label, folder in (("historical_prompt_1_0", archive), ("prompt_1_1", new_dir)):
        audit = [sys.executable, "-m", "ai_generator.cli", "audit", "--spec", relative(spec_path),
                 "--tests", relative(folder / "generated_tests.json"),
                 "--generation-report", relative(folder / "generation_report.json"),
                 "--hypotheses", relative(folder / "hypothetical_scenarios.json"),
                 "--output", relative(folder / "audit.json")]
        metadata["audit_exit_codes"][label] = run_command(audit, root, folder / "audit_command.log")
    changed = [relative(path) for path, digest in preserved.items() if not path.is_file() or sha256(path) != digest]
    metadata["historical_sources_unchanged"] = not changed
    metadata["changed_historical_files"] = changed
    metadata["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(run_dir / "experiment_metadata.json", metadata)
    print(json.dumps({"experiment": relative(run_dir), "generation_exit_code": metadata["generation_exit_code"],
                      "audit_exit_codes": metadata["audit_exit_codes"], "historical_sources_unchanged": not changed}, indent=2), flush=True)
    if changed or metadata["generation_exit_code"] or any(metadata["audit_exit_codes"].values()):
        raise SystemExit(1)
    summarize_experiment(run_dir)


if __name__ == "__main__":
    main()
