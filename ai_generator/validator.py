"""Structural and conservative semantic checks; uncertain cases never enter exports."""

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from .errors import OutputError
from .json_utils import canonical, loads_json
from .openapi_parser import Operation, ParsedSpec, is_json_media, json_schema
from .schemas import TestCase, TestSuite


@dataclass
class ValidationResult:
    outcome: Literal["accepted", "rejected", "hypothetical"]
    reasons: list[str] = field(default_factory=list)
    request_violations: list[str] = field(default_factory=list)


def validate_contract(raw: str) -> TestSuite:
    try:
        return TestSuite.model_validate(loads_json(raw))
    except ValidationError as exc:
        raise OutputError("JSON does not match integration contract v1.0") from exc


def _schema_errors(value: Any, schema: Any, operation: Operation) -> list[str]:
    validator = Draft202012Validator(json_schema(schema, version=operation.version), format_checker=FormatChecker())
    return [f"{error.validator} at /{'/'.join(map(str, error.absolute_path))}" for error in validator.iter_errors(value)]


def _subset(value: Any, expected: Any) -> bool:
    if isinstance(value, dict) and isinstance(expected, dict):
        return all(key in expected and _subset(item, expected[key]) for key, item in value.items())
    return canonical(value) == canonical(expected)


def _request(case: TestCase) -> dict:
    return {"path_params": case.path_params, "query_params": case.query_params,
            "headers": {key.lower(): value for key, value in case.headers.items()}, "body": case.body}


def _scenario_request(request: dict) -> dict:
    return {"path_params": request.get("path_params", {}), "query_params": request.get("query_params", {}),
            "headers": {key.lower(): value for key, value in request.get("headers", {}).items()},
            "body": request.get("body")}


def _boundary(value: Any, schema: Any) -> bool:
    if not isinstance(schema, dict):
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if any(bound in schema and not isinstance(schema[bound], bool) and value == schema[bound] for bound in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")):
            return True
        if any(bound in schema and not isinstance(schema[bound], bool) and abs(value - schema[bound]) <= 1 and value != schema[bound] for bound in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")):
            return True
    if isinstance(value, (str, list)):
        bounds = ("minLength", "maxLength") if isinstance(value, str) else ("minItems", "maxItems")
        if any(key in schema and abs(len(value) - schema[key]) <= 1 for key in bounds):
            return True
    if isinstance(value, dict) and any(_boundary(item, schema.get("properties", {}).get(key, {})) for key, item in value.items()):
        return True
    if isinstance(value, list) and any(_boundary(item, schema.get("items", {})) for item in value):
        return True
    return any(_boundary(value, part) for key in ("allOf", "oneOf", "anyOf") for part in schema.get(key, []))


def _partial_schema(schema: Any) -> Any:
    if isinstance(schema, dict):
        result = {key: value for key, value in schema.items() if key not in {"required", "minProperties", "dependentRequired"}}
        if "properties" in result:
            result["properties"] = {key: _partial_schema(value) for key, value in result["properties"].items()}
        for key in ("items", "additionalProperties"):
            if key in result:
                result[key] = _partial_schema(result[key])
        for key in ("allOf", "anyOf", "oneOf"):
            if key in result:
                result[key] = [_partial_schema(value) for value in result[key]]
        return result
    if isinstance(schema, list):
        return [_partial_schema(item) for item in schema]
    return schema


class SemanticValidator:
    def __init__(self, spec: ParsedSpec):
        self.spec = spec

    def validate(self, case: TestCase, *, operation: Operation | None = None) -> ValidationResult:
        op = self.spec.find(case.method, case.endpoint)
        if op is None:
            return ValidationResult("rejected", ["Endpoint/method does not exist in OpenAPI"])
        if operation is not None and op.key != operation.key:
            return ValidationResult("rejected", ["Candidate does not belong to the requested operation"])
        variables = set(re.findall(r"\{([^{}]+)\}", case.endpoint))
        if set(case.path_params) != variables:
            return ValidationResult("rejected", ["path_params must match every path variable exactly (v1.0 limitation)"])
        status = str(case.expected_status)
        if status not in op.responses:
            # default/2XX document families, but never justify a particular concrete code.
            fallback = status[0] + "XX" in op.responses or "default" in op.responses
            return ValidationResult("hypothetical" if fallback else "rejected", ["Concrete expected status is not explicitly documented"])
        headers = {key.lower(): value for key, value in case.headers.items()}
        matches = [scenario for scenario in op.scenarios
                   if canonical(_scenario_request(scenario["request"])) == canonical(_request(case))
                   and scenario["expected_status"] == case.expected_status]
        violations: list[str] = []
        boundary = False
        for parameter in op.parameters:
            location, name = parameter["in"], parameter["name"]
            if location == "cookie":
                continue
            values = {"path": case.path_params, "query": case.query_params, "header": headers}[location]
            lookup = name.lower() if location == "header" else name
            if lookup not in values:
                if parameter.get("required"):
                    violations.append(f"Missing required {location} parameter: {name}")
                continue
            value = values[lookup]
            schema = parameter.get("schema", {})
            # Header wire values are strings. Typed header conversion is ambiguous.
            if location == "header" and isinstance(schema, dict) and schema.get("type", "string") != "string":
                return ValidationResult("hypothetical", ["Non-string header serialization is unsupported"])
            violations.extend(f"{location}.{name}: {error}" for error in _schema_errors(value, schema, op))
            boundary = boundary or _boundary(value, schema)
        if case.body is not None:
            if op.request_body is None:
                return ValidationResult("rejected", ["Body supplied for an operation without requestBody"])
            content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if not content_type:
                violations.append("Missing Content-Type for JSON body")
            media = op.request_body["content"].get(content_type)
            if media is None or not is_json_media(content_type):
                # Content negotiation failures do not follow from JSON schema validation.
                if not matches:
                    return ValidationResult("hypothetical", ["Request media type is absent or unsupported"], violations)
                violations.append("Unsupported or missing request Content-Type")
                if case.test_type == "positive":
                    return ValidationResult("rejected", ["Positive case must represent a supported JSON Content-Type"], violations)
            else:
                body_schema = media.get("schema", {})
                violations.extend(f"body: {error}" for error in _schema_errors(case.body, body_schema, op))
                boundary = boundary or _boundary(case.body, body_schema)
        elif op.request_body and op.request_body.get("required"):
            violations.append("Missing required request body")
        success = 200 <= case.expected_status <= 299
        if case.test_type == "positive" and (violations or not success):
            return ValidationResult("rejected", ["Positive case violates its schema or expects a non-success response"], violations)
        if case.test_type == "negative" and success:
            return ValidationResult("rejected", ["Negative case expects a success response"], violations)
        if case.test_type == "boundary" and not boundary:
            return ValidationResult("rejected", ["Boundary case does not exercise a declared constraint boundary"], violations)
        if case.test_type == "boundary" and violations and success:
            return ValidationResult("rejected", ["Invalid boundary request expects success"], violations)
        declared_query = {p["name"] for p in op.parameters if p["in"] == "query"}
        declared_headers = {p["name"].lower() for p in op.parameters if p["in"] == "header"}
        if (set(case.query_params) - declared_query or set(headers) - declared_headers - {"content-type", "accept"}) and not matches:
            return ValidationResult("hypothetical", ["Undeclared query/header inputs need concrete scenario evidence"], violations)
        if op.unsupported:
            return ValidationResult("hypothetical", op.unsupported, violations)
        if violations and not matches and case.expected_status != op.validation_error_status:
            return ValidationResult("hypothetical", ["No documented mapping from these request violations to this status"], violations)
        if not success and not matches and not (violations and case.expected_status == op.validation_error_status):
            return ValidationResult("hypothetical", ["No concrete documented scenario justifies this error"], violations)
        if success and not matches:
            if case.path_params or case.method == "DELETE":
                return ValidationResult("hypothetical", ["Resource existence/state is not established by OpenAPI"], violations)
            successes = [code for code in op.responses if code.isdigit() and 200 <= int(code) <= 299]
            if len(successes) != 1:
                return ValidationResult("hypothetical", ["Multiple success statuses need a concrete scenario"], violations)
        if case.expected_body is not None:
            if not matches or not any(isinstance(s.get("expected_body"), dict) and _subset(case.expected_body, s["expected_body"]) for s in matches):
                return ValidationResult("hypothetical", ["Concrete response assertion values lack scenario evidence"], violations)
            content = op.responses[status].get("content", {})
            schemas = [value.get("schema", {}) for media, value in content.items() if is_json_media(media)]
            if not schemas:
                return ValidationResult("rejected", ["No documented JSON response for expected_body"], violations)
            for schema in schemas:
                partial = _partial_schema(json_schema(schema, "response", op.version))
                if not list(Draft202012Validator(partial, format_checker=FormatChecker()).iter_errors(case.expected_body)):
                    break
            else:
                return ValidationResult("rejected", ["expected_body subset conflicts with the response schema"], violations)
        return ValidationResult("accepted", ["Exact documented scenario" if matches else "Schema and explicit response evidence"], violations)
