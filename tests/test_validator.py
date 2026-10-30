import copy
import json

import pytest
from pydantic import ValidationError

from ai_generator.errors import OutputError
from ai_generator.openapi_parser import OpenAPIParser
from ai_generator.schemas import TestCase, TestSuite
from ai_generator.validator import SemanticValidator, validate_contract


def test_all_demo_cases_including_intentional_invalid(spec, cases):
    validator = SemanticValidator(spec)
    for item in cases:
        result = validator.validate(TestCase.model_validate(item))
        assert result.outcome == "accepted", result
    assert validator.validate(TestCase.model_validate(cases[-1])).request_violations
    assert validator.validate(TestCase.model_validate(cases[-2])).request_violations


@pytest.mark.parametrize("change", [
    {"expected_status": "200"}, {"expected_status": True}, {"extra": 1}, {"test_type": "nominal"},
    {"endpoint": "https://example.com/products"}, {"endpoint": "//evil.invalid/x"},
    {"method": "get"}, {"body": float("nan")}, {"headers": {"X": "one", "x": "two"}},
    {"headers": {"X": "bad\r\nvalue"}}, {"headers": {"bad header": "x"}},
])
def test_contract_rejects_invalid_types_fields(cases, change):
    with pytest.raises(ValidationError):
        TestCase.model_validate({**cases[0], **change})


def test_missing_contract_fields_and_unique_ids(cases):
    case = cases[0]
    case.pop("body")
    with pytest.raises(ValidationError):
        TestCase.model_validate(case)
    with pytest.raises(ValidationError, match="unique"):
        TestSuite(schema_version="1.0", tests=[TestCase.model_validate(cases[1])] * 2)


def test_validate_contract_envelope(cases):
    assert len(validate_contract(json.dumps({"schema_version": "1.0", "tests": [cases[0]]})).tests) == 1
    with pytest.raises(OutputError):
        validate_contract('{"schema_version":"2.0","tests":[]}')


@pytest.mark.parametrize("change", [
    {"endpoint": "/absent"}, {"method": "DELETE"}, {"path_params": {}},
    {"path_params": {"id": 1, "extra": 2}}, {"expected_status": 418},
    {"test_type": "negative"}, {"test_type": "boundary", "path_params": {"id": 5}},
    {"path_params": {"id": "one"}}, {"body": {"extra": 1}},
])
def test_semantic_rejection(spec, cases, change):
    result = SemanticValidator(spec).validate(TestCase.model_validate({**cases[0], **change}))
    assert result.outcome == "rejected", result


def test_resource_state_unknown_is_hypothetical(spec, cases):
    case = TestCase.model_validate({**cases[0], "path_params": {"id": 47}, "expected_body": None})
    assert SemanticValidator(spec).validate(case).outcome == "hypothetical"


def test_error_presence_does_not_imply_mapping(spec, cases):
    spec.operations[1].scenarios = []
    spec.operations[1].validation_error_status = None
    case = TestCase.model_validate(cases[-1])
    assert SemanticValidator(spec).validate(case).outcome == "hypothetical"


def test_negative_missing_required_header_is_intentional(spec, cases):
    spec.operations[1].scenarios = []
    spec.operations[1].parameters.append({"name": "X-Trace", "in": "header", "required": True, "schema": {"type": "string"}})
    case = TestCase.model_validate({**cases[3], "test_type": "negative", "expected_status": 422})
    result = SemanticValidator(spec).validate(case)
    assert result.outcome == "accepted" and result.request_violations


def test_required_header_case_insensitive(spec, cases):
    spec.operations[1].parameters.append({"name": "X-Trace", "in": "header", "required": True, "schema": {"type": "string"}})
    case = TestCase.model_validate({**cases[3], "headers": {"content-type": "application/json", "x-trace": "demo"}})
    assert SemanticValidator(spec).validate(case).outcome == "accepted"


def test_response_assertion_requires_documented_value(spec, cases):
    case = TestCase.model_validate({**cases[0], "expected_body": {"id": 123}})
    assert SemanticValidator(spec).validate(case).outcome == "hypothetical"


def test_subset_response_does_not_require_all_properties(spec, cases):
    case = TestCase.model_validate(cases[0])
    assert case.expected_body == {"id": 1}
    assert SemanticValidator(spec).validate(case).outcome == "accepted"


def test_response_assertion_still_checks_types(spec, cases):
    spec.operations[0].scenarios[0]["expected_body"] = {"id": "one"}
    case = TestCase.model_validate({**cases[0], "expected_body": {"id": "one"}})
    assert SemanticValidator(spec).validate(case).outcome == "rejected"


def test_default_response_is_uncertain(spec, cases):
    spec.operations[0].responses["default"] = {"description": "Any other error"}
    case = TestCase.model_validate({**cases[1], "expected_status": 409})
    assert SemanticValidator(spec).validate(case).outcome == "hypothetical"


def test_unknown_query_is_uncertain(spec, cases):
    case = TestCase.model_validate({**cases[3], "query_params": {"unknown": "x"}})
    assert SemanticValidator(spec).validate(case).outcome == "hypothetical"


def test_security_is_uncertain(document, save_spec, cases):
    document["security"] = [{"bearerAuth": []}]
    parsed = OpenAPIParser().parse(save_spec(document))
    assert parsed.warnings
    assert SemanticValidator(parsed).validate(TestCase.model_validate(cases[0])).outcome == "hypothetical"


@pytest.mark.parametrize("schema, valid, invalid", [
    ({"type": "string", "enum": ["a", "b"]}, "a", "c"),
    ({"type": "string", "format": "email"}, "demo@example.com", "not-email"),
    ({"type": "string", "minLength": 2, "maxLength": 4}, "abc", "x"),
    ({"type": ["string", "null"]}, None, 7),
    ({"type": "integer", "minimum": 0, "exclusiveMaximum": 10}, 9, 10),
    ({"anyOf": [{"type": "string"}, {"type": "null"}]}, None, []),
])
def test_query_schema_constraints_31(spec, cases, schema, valid, invalid):
    op = spec.operations[1]
    op.version = "3.1.0"
    op.parameters = [{"in": "query", "name": "q", "required": True, "schema": schema}]
    for value, expected in [(valid, "accepted"), (invalid, "rejected")]:
        case = TestCase.model_validate({**cases[3], "query_params": {"q": value}})
        assert SemanticValidator(spec).validate(case).outcome == expected


def test_nested_response_subset(spec, cases):
    op = spec.operations[0]
    op.responses["200"]["content"]["application/json"]["schema"] = {
        "type": "object", "required": ["outer"], "properties": {
            "outer": {"type": "object", "required": ["a", "b"], "properties": {"a": {"type": "integer"}, "b": {"type": "string"}}}}}
    op.scenarios[0]["expected_body"] = {"outer": {"a": 1}}
    case = TestCase.model_validate({**cases[0], "expected_body": {"outer": {"a": 1}}})
    assert SemanticValidator(spec).validate(case).outcome == "accepted"


def test_missing_content_type_only_with_exact_error_evidence(spec, cases):
    op = spec.operations[1]
    op.responses["415"] = {"description": "Missing media type"}
    case = TestCase.model_validate({**cases[3], "headers": {}, "test_type": "negative", "expected_status": 415})
    validator = SemanticValidator(spec)
    assert validator.validate(case).outcome == "hypothetical"
    op.scenarios.append({"request": {"body": case.body}, "expected_status": 415})
    assert validator.validate(case).outcome == "accepted"


def test_missing_required_query_and_body_can_be_negative(spec, cases):
    op = spec.operations[1]
    op.parameters = [{"name": "limit", "in": "query", "required": True, "schema": {"type": "integer", "minimum": 1}}]
    case = TestCase.model_validate({**cases[3], "body": None, "test_type": "negative", "expected_status": 422})
    result = SemanticValidator(spec).validate(case)
    assert result.outcome == "accepted"
    assert len(result.request_violations) == 2
