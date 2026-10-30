import pytest

from ai_generator.errors import SpecError
from ai_generator.openapi_parser import OpenAPIParser, json_schema


def test_json_local_refs_required_constraints(spec):
    assert len(spec.operations) == 2
    get, post = spec.operations
    assert get.parameters[0]["required"] is True
    assert get.parameters[0]["schema"]["minimum"] == 1
    body = post.request_body["content"]["application/json"]["schema"]
    assert body["required"] == ["name", "price"]
    assert body["properties"]["price"]["maximum"] == 10000
    assert len(spec.sha256) == 64
    assert "$ref" not in str(body)


def test_yaml(document, save_spec):
    parsed = OpenAPIParser().parse(save_spec(document, ".yaml"))
    assert {op.method for op in parsed.operations} == {"GET", "POST"}


@pytest.mark.parametrize("version", ["3.0.3", "3.1.0"])
def test_versions(document, save_spec, version):
    document["openapi"] = version
    assert OpenAPIParser().parse(save_spec(document)).version == version


@pytest.mark.parametrize("reference, expected", [
    ("#/components/schemas/ProductInput", "Circular"),
    ("#/components/schemas/Absent", "Unresolved"),
    ("https://example.invalid/schema.json", "External"),
])
def test_reference_errors(document, save_spec, reference, expected):
    document["components"]["schemas"]["ProductInput"] = {"$ref": reference}
    with pytest.raises(SpecError, match=expected):
        OpenAPIParser().parse(save_spec(document))


def test_pointer_escapes(document, save_spec):
    document["components"]["schemas"]["a/b~c"] = {"type": "string"}
    document["components"]["schemas"]["ProductInput"] = {"$ref": "#/components/schemas/a~1b~0c"}
    body = OpenAPIParser().parse(save_spec(document)).operations[1].request_body
    assert body["content"]["application/json"]["schema"] == {"type": "string"}


def test_operation_parameter_override(document, save_spec):
    document["paths"]["/products/{id}"]["get"]["parameters"] = [
        {"name": "id", "in": "path", "required": True, "schema": {"type": "integer", "minimum": 5}}]
    parsed = OpenAPIParser().parse(save_spec(document))
    assert len(parsed.operations[0].parameters) == 1
    assert parsed.operations[0].parameters[0]["schema"]["minimum"] == 5


@pytest.mark.parametrize("section", ["info", "paths", "openapi"])
def test_missing_required_sections(document, save_spec, section):
    document.pop(section)
    with pytest.raises(SpecError):
        OpenAPIParser().parse(save_spec(document))


def test_invalid_schema(document, save_spec):
    document["components"]["schemas"]["ProductInput"]["properties"]["price"]["minimum"] = "zero"
    with pytest.raises(SpecError, match="schema"):
        OpenAPIParser().parse(save_spec(document))


@pytest.mark.parametrize("text", ['{"openapi":"3.0.3","openapi":"3.1.0"}', "x: 1\nx: 2\n", "x: &x [*x]", "x: .nan", "!!python/object:evil {}"])
def test_unsafe_invalid_input(tmp_path, text):
    path = tmp_path / ("invalid.json" if text.startswith("{") else "invalid.yaml")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(SpecError):
        OpenAPIParser().parse(path)


def test_31_ref_siblings_preserve_constraints(document, save_spec):
    document["openapi"] = "3.1.0"
    schema = document["paths"]["/products"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    schema["minProperties"] = 2
    parsed = OpenAPIParser().parse(save_spec(document))
    assert "allOf" in parsed.operations[1].request_body["content"]["application/json"]["schema"]


def test_31_reference_description_sibling(document, save_spec):
    document["openapi"] = "3.1.0"
    document["paths"]["/products/{id}"]["parameters"][0]["description"] = "Safe override"
    parsed = OpenAPIParser().parse(save_spec(document))
    assert parsed.operations[0].parameters[0]["name"] == "id"


def test_dynamic_refs_refused(document, save_spec):
    document["components"]["schemas"]["ProductInput"] = {"$dynamicRef": "https://evil.invalid/schema"}
    with pytest.raises(SpecError, match="Dynamic"):
        OpenAPIParser().parse(save_spec(document))


@pytest.mark.parametrize("name", ["default", "example", "examples", "$ref"])
def test_schema_property_names_are_literal(document, save_spec, name):
    document["components"]["schemas"]["Text"] = {"type": "string", "minLength": 1}
    body = document["components"]["schemas"]["ProductInput"]
    body["properties"][name] = {"$ref": "#/components/schemas/Text"}
    parsed = OpenAPIParser().parse(save_spec(document))
    properties = parsed.operations[1].request_body["content"]["application/json"]["schema"]["properties"]
    assert properties[name] == {"type": "string", "minLength": 1}


def test_nullable_exclusive_and_direction():
    schema = json_schema({"type": "number", "nullable": True, "minimum": 0, "exclusiveMinimum": True})
    assert schema["type"] == ["number", "null"]
    assert schema["exclusiveMinimum"] == 0 and "minimum" not in schema
    obj = {"type": "object", "required": ["id", "password"], "properties": {"id": {"readOnly": True}, "password": {"writeOnly": True}}}
    assert json_schema(obj)["required"] == ["password"]
    assert json_schema(obj, "response")["required"] == ["id"]


@pytest.mark.parametrize("method", ["put", "patch", "delete", "head", "options", "trace"])
def test_http_methods(document, save_spec, method):
    document["paths"]["/products"][method] = {"responses": {"204": {"description": "Success"}}}
    assert any(op.method == method.upper() for op in OpenAPIParser().parse(save_spec(document)).operations)
