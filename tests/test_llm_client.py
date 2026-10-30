import json

import httpx
import pytest

from ai_generator.config import LLMConfig
from ai_generator.errors import LLMError, OutputError
from ai_generator.llm_client import LiveLLMClient, MockLLMClient, extract_envelope


def config(**changes):
    return LLMConfig(api_key="offline-test-key", base_url="https://provider.invalid/v1", model="fixture-model", **changes)


def completion(content, finish="stop"):
    return {"choices": [{"finish_reason": finish, "message": {"content": content}}]}


def test_real_client_request_over_fake_http(spec, cases):
    requests = []
    def handler(request):
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer offline-test-key"
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json=completion(json.dumps({"schema_version": "1.0", "tests": cases[:1]})))
    client = LiveLLMClient(config(), transport=httpx.MockTransport(handler))
    result = client.generate([], spec.operations[0], spec, 3)
    assert result.data["tests"][0] == cases[0]
    assert result.attempts == client.attempts == 1
    assert str(requests[0].url) == "https://provider.invalid/v1/chat/completions"


@pytest.mark.parametrize("status", [429, 500, 503, 408])
def test_transient_http_retry(spec, status):
    requests, delays = [], []
    def handler(request):
        requests.append(request)
        return httpx.Response(status) if len(requests) < 3 else httpx.Response(200, json=completion('{"schema_version":"1.0","tests":[]}'))
    client = LiveLLMClient(config(), transport=httpx.MockTransport(handler), sleep=delays.append)
    assert client.generate([], spec.operations[0], spec, 3).attempts == 3
    assert delays == [1, 2]


@pytest.mark.parametrize("status", [400, 401, 403, 404, 302])
def test_permanent_error_no_retry_no_secret(spec, status):
    client = LiveLLMClient(config(), transport=httpx.MockTransport(lambda r: httpx.Response(status, text="offline-test-key")))
    with pytest.raises(LLMError) as exc:
        client.generate([], spec.operations[0], spec, 3)
    assert client.attempts == 1
    assert "offline-test-key" not in str(exc.value)


def test_timeout_exhaustion(spec):
    delays = []
    def handler(request):
        raise httpx.ReadTimeout("secret provider detail", request=request)
    client = LiveLLMClient(config(), transport=httpx.MockTransport(handler), sleep=delays.append)
    with pytest.raises(LLMError, match="timed out.*3 attempt"):
        client.generate([], spec.operations[0], spec, 3)
    assert client.attempts == 3 and delays == [1, 2]


@pytest.mark.parametrize("body", [completion("not json"), completion("{}"), completion("{}", "length"), {"choices": []}])
def test_invalid_responses_bounded_retry(spec, body):
    client = LiveLLMClient(config(max_retries=1), transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)), sleep=lambda s: None)
    with pytest.raises(LLMError):
        client.generate([], spec.operations[0], spec, 3)
    assert client.attempts == 2


def test_invalid_response_available_for_optin_log(spec):
    client = LiveLLMClient(config(max_retries=0), transport=httpx.MockTransport(lambda r: httpx.Response(200, json=completion("broken-json"))))
    with pytest.raises(LLMError) as error:
        client.generate([], spec.operations[0], spec, 3)
    assert error.value.raw_response == "broken-json"


@pytest.mark.parametrize("raw", ["```json\n{}\n```", '{"schema_version":"1.0","tests":[],"x":1}', '{"a":1,"a":2}', '{"x":NaN}', '{"x":1e999}', '[]'])
def test_safe_extraction(raw):
    with pytest.raises(OutputError):
        extract_envelope(raw)


def test_missing_key():
    with pytest.raises(LLMError, match="requires"):
        LiveLLMClient(LLMConfig())


def test_mock_recording_and_spec_drift(spec):
    client = MockLLMClient()
    assert len(client.generate([], spec.operations[0], spec, 2).data["tests"]) == 2
    assert client.attempts == 0
    spec.operations[0].parameters[0]["schema"]["minimum"] = 100
    with pytest.raises(LLMError, match="matching mock"):
        client.generate([], spec.operations[0], spec, 3)


@pytest.mark.parametrize("output_format", ["json_schema", "none"])
def test_output_modes(spec, output_format):
    def handler(request):
        payload = json.loads(request.content)
        if output_format == "none":
            assert "response_format" not in payload
        else:
            assert payload["response_format"]["json_schema"]["strict"] is False
        return httpx.Response(200, json=completion('{"schema_version":"1.0","tests":[]}'))
    client = LiveLLMClient(config(response_format=output_format), transport=httpx.MockTransport(handler))
    client.generate([], spec.operations[0], spec, 3)
