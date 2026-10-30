"""Small synchronous Chat Completions client; injected HTTP transport for offline tests."""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx

from .config import LLMConfig
from .errors import LLMError, OutputError
from .json_utils import canonical, loads_json
from .openapi_parser import Operation, ParsedSpec
from .schemas import TestSuite


@dataclass
class LLMResult:
    data: dict[str, Any]
    raw: str
    attempts: int
    duration_seconds: float
    model: str
    mode: str


def extract_envelope(raw: str) -> dict:
    data = loads_json(raw)
    if not isinstance(data, dict) or set(data) != {"schema_version", "tests"} or data["schema_version"] != "1.0" or not isinstance(data["tests"], list):
        raise OutputError("Expected exactly schema_version='1.0' and tests array")
    if len(data["tests"]) > 500:
        raise OutputError("Response exceeds 500 candidates")
    return data


class LiveLLMClient:
    mode = "live"

    def __init__(self, config: LLMConfig, *, transport: httpx.BaseTransport | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        if not config.api_key.get_secret_value() or not config.base_url or not config.model:
            raise LLMError("Live mode requires LLM_API_KEY, LLM_BASE_URL and LLM_MODEL")
        self.config = config
        self.model = config.model
        self.transport = transport
        self.sleep = sleep
        self.attempts = 0

    def generate(self, messages: list[dict[str, str]], operation: Operation,
                 spec: ParsedSpec, target: int) -> LLMResult:
        payload: dict = {"model": self.model, "messages": messages,
                         "temperature": self.config.temperature, "max_tokens": self.config.max_tokens}
        if self.config.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif self.config.response_format == "json_schema":
            # Best effort: arbitrary property maps in v1.0 are not compatible with
            # all providers' strict JSON Schema subsets. Local validation is mandatory.
            payload["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "api_test_suite_v1", "strict": False, "schema": TestSuite.model_json_schema()}}
        start = time.perf_counter()
        problem = "LLM request failed"
        last_raw: str | None = None
        with httpx.Client(transport=self.transport, timeout=self.config.timeout,
                          follow_redirects=False, trust_env=False) as client:
            for attempt in range(self.config.max_retries + 1):
                self.attempts += 1
                retry = True
                try:
                    response = client.post(self.config.base_url + "/chat/completions", json=payload,
                                           headers={"Authorization": "Bearer " + self.config.api_key.get_secret_value()})
                    if response.status_code >= 400:
                        problem = f"LLM provider returned HTTP {response.status_code}"
                        retry = response.status_code in {408, 429} or response.status_code >= 500
                    elif response.status_code != 200:
                        problem, retry = "Unexpected LLM HTTP status (redirects are disabled)", False
                    else:
                        envelope = loads_json(response.text)
                        choice = envelope["choices"][0]
                        message = choice["message"]
                        if isinstance(message.get("content"), str):
                            last_raw = message["content"]
                        if message.get("refusal"):
                            problem, retry = "LLM refused the generation request", False
                        elif choice.get("finish_reason") != "stop":
                            problem = "LLM response incomplete or interrupted"
                        else:
                            raw = message["content"]
                            if not isinstance(raw, str):
                                raise OutputError("Missing textual JSON response")
                            return LLMResult(extract_envelope(raw), raw, attempt + 1,
                                             time.perf_counter() - start, self.model, self.mode)
                except httpx.TimeoutException:
                    problem = "LLM request timed out"
                except httpx.RequestError:
                    problem = "Cannot connect to the LLM provider"
                except (OutputError, KeyError, IndexError, TypeError, AttributeError):
                    problem = "LLM returned invalid JSON or an invalid response envelope"
                if not retry or attempt == self.config.max_retries:
                    raise LLMError(f"{problem}; {attempt + 1} attempt(s). Check provider/model/JSON mode configuration.", raw_response=last_raw)
                self.sleep(min(2 ** attempt, 8))
        raise LLMError(problem)  # defensive; all bounded attempts return or raise


class MockLLMClient:
    """Recorded data for a specific normalized spec, never an LLM fallback."""

    mode = "mock"

    def __init__(self, fixture: str | Path | None = None):
        path = Path(fixture) if fixture else Path(__file__).parent / "fixtures" / "products_recording.json"
        try:
            self.recording = loads_json(path.read_text(encoding="utf-8"))
            self.model = self.recording["model"]
            if not isinstance(self.recording["operations"], dict):
                raise ValueError
        except (OSError, ValueError, KeyError, TypeError, OutputError) as exc:
            raise LLMError("Invalid or unreadable mock recording") from exc
        self.attempts = 0

    def generate(self, messages: list[dict[str, str]], operation: Operation,
                 spec: ParsedSpec, target: int) -> LLMResult:
        recorded = self.recording["operations"].get(operation.key)
        if not isinstance(recorded, dict) or canonical(recorded.get("operation")) != canonical(operation.prompt_data()):
            raise LLMError("No matching mock recording for this operation/spec; provide --mock-fixture or use live mode")
        # Playback is deliberately not counted as a real LLM attempt.
        data = {"schema_version": "1.0", "tests": recorded["tests"][:target]}
        raw = canonical(data)
        return LLMResult(extract_envelope(raw), raw, 0, 0.0, self.model, self.mode)
