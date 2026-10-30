"""OpenAPI 3.0/3.1 loader and local-reference normalizer (never performs HTTP)."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import yaml
from jsonschema import Draft202012Validator

from .errors import OutputError, SpecError
from .json_utils import loads_json

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
DATA_FIELDS = {"example", "examples", "default", "enum", "const"}


class UniqueSafeLoader(yaml.SafeLoader):
    """Safe YAML without ambiguous duplicate keys."""


def _yaml_mapping(loader: UniqueSafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    loader.flatten_mapping(node)
    result: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, (str, int)) or isinstance(key, bool) or key in result:
            raise SpecError("YAML object key is invalid or duplicated")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _yaml_mapping)


def _check_tree(document: Any) -> None:
    pending = [(document, frozenset(), 0)]
    count = 0
    while pending:
        node, ancestors, depth = pending.pop()
        count += 1
        if count > 100_000 or depth > 100:
            raise SpecError("OpenAPI tree/alias expansion exceeds size or depth limits")
        if isinstance(node, (dict, list)):
            if id(node) in ancestors:
                raise SpecError("Circular YAML alias")
            children = node.values() if isinstance(node, dict) else node
            pending.extend((child, ancestors | {id(node)}, depth + 1) for child in children)


def json_schema(schema: Any, direction: str = "request", version: str = "3.0") -> Any:
    """Translate common OAS 3.0 keywords and directional required fields."""
    if not isinstance(schema, dict):
        return schema
    result = dict(schema)
    if version.startswith("3.0"):
        if result.pop("nullable", False) and "type" in result:
            result["type"] = [result["type"], "null"]
        for bound in ("minimum", "maximum"):
            exclusive = "exclusive" + bound.capitalize()
            if isinstance(result.get(exclusive), bool):
                enabled = result.pop(exclusive)
                if enabled and bound in result:
                    result[exclusive] = result.pop(bound)
    properties = result.get("properties", {})
    if isinstance(properties, dict):
        result["properties"] = {key: json_schema(value, direction, version) for key, value in properties.items()}
        ignored = "readOnly" if direction == "request" else "writeOnly"
        if "required" in result:
            result["required"] = [key for key in result["required"] if not isinstance(properties.get(key), dict) or not properties[key].get(ignored)]
    for key in ("items", "additionalProperties", "not", "if", "then", "else", "contains"):
        if key in result:
            result[key] = json_schema(result[key], direction, version)
    for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
        if key in result:
            result[key] = [json_schema(value, direction, version) for value in result[key]]
    return result


@dataclass
class Operation:
    method: str
    endpoint: str
    parameters: list[dict]
    request_body: dict | None
    responses: dict[str, dict]
    description: str = ""
    scenarios: list[dict] = field(default_factory=list)
    validation_error_status: int | None = None
    unsupported: list[str] = field(default_factory=list)
    version: str = "3.0"

    @property
    def key(self) -> str:
        return f"{self.method} {self.endpoint}"

    def prompt_data(self) -> dict:
        return {
            "method": self.method, "endpoint": self.endpoint, "description": self.description,
            "parameters": self.parameters, "requestBody": self.request_body,
            "responses": self.responses, "x-test-scenarios": self.scenarios,
            "x-validation-error-status": self.validation_error_status,
            "unsupported": self.unsupported,
        }


@dataclass
class ParsedSpec:
    operations: list[Operation]
    sha256: str
    version: str
    warnings: list[str]

    def find(self, method: str, endpoint: str) -> Operation | None:
        return next((op for op in self.operations if op.method == method and op.endpoint == endpoint), None)


class OpenAPIParser:
    def parse(self, path: str | Path) -> ParsedSpec:
        try:
            raw = Path(path).read_bytes()
            if len(raw) > 5_000_000:
                raise SpecError("OpenAPI input exceeds 5 MB")
            text = raw.decode("utf-8-sig")
            if Path(path).suffix.lower() == ".json":
                document = loads_json(text, max_bytes=5_000_000)
            else:
                document = yaml.load(text, Loader=UniqueSafeLoader)
            # Bound alias expansion before serialization. Normalize YAML status keys.
            _check_tree(document)
            document = loads_json(json.dumps(document, allow_nan=False, ensure_ascii=False), max_bytes=10_000_000)
        except (OSError, UnicodeError, ValueError, TypeError, RecursionError, yaml.YAMLError, OutputError) as exc:
            raise SpecError("Cannot load OpenAPI: invalid JSON/YAML, encoding or unreadable file") from exc
        if not isinstance(document, dict):
            raise SpecError("OpenAPI root must be an object")
        version = document.get("openapi", "")
        if not isinstance(version, str) or not re.fullmatch(r"3\.[01]\.\d+", version):
            raise SpecError("Only OpenAPI 3.0.x and 3.1.x are supported")
        info = document.get("info")
        if not isinstance(info, dict) or not all(isinstance(info.get(k), str) and info[k] for k in ("title", "version")):
            raise SpecError("info.title and info.version are required strings")
        if not isinstance(document.get("paths"), dict):
            raise SpecError("paths must be an object")
        self._resolved_nodes = 0
        resolved = self._resolve(document, document, (), 0)
        operations: list[Operation] = []
        warnings: list[str] = []
        try:
            for endpoint, item in resolved["paths"].items():
                if endpoint.startswith("x-"):
                    continue
                if not endpoint.startswith("/") or endpoint.startswith("//") or re.search(r"[\s?#]", endpoint) or not isinstance(item, dict):
                    raise SpecError("Invalid OpenAPI path item")
                if re.search(r"[{}]", re.sub(r"\{[^{}]+\}", "", endpoint)):
                    raise SpecError("Malformed path variable template")
                for method, data in item.items():
                    if method.lower() not in HTTP_METHODS:
                        continue
                    if method != method.lower() or not isinstance(data, dict):
                        raise SpecError("Operation must be an object with a lowercase HTTP method")
                    op = self._operation(endpoint, method, item, data, resolved, version)
                    operations.append(op)
                    warnings.extend(f"{op.key}: {reason}" for reason in op.unsupported)
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise SpecError("Malformed operation, parameter, requestBody or response") from exc
        if not operations:
            raise SpecError("No supported HTTP operation found")
        return ParsedSpec(operations, hashlib.sha256(raw).hexdigest(), version, warnings)

    def _resolve(self, node: Any, root: dict, stack: tuple[str, ...], depth: int, schema_context: bool = False) -> Any:
        self._resolved_nodes += 1
        if self._resolved_nodes > 200_000:
            raise SpecError("Resolved OpenAPI tree exceeds 200 000 nodes")
        if depth > 100:
            raise SpecError("Reference/document nesting exceeds 100 levels")
        if isinstance(node, list):
            return [self._resolve(value, root, stack, depth + 1, schema_context) for value in node]
        if not isinstance(node, dict):
            return node
        if any(key in node for key in ("$dynamicRef", "$recursiveRef", "$id", "$anchor", "$dynamicAnchor")):
            raise SpecError("Dynamic references, schema identifiers and anchors are unsupported")
        if "$ref" in node:
            ref = node["$ref"]
            if not isinstance(ref, str) or not ref.startswith("#/"):
                raise SpecError("External and non-pointer references are unsupported")
            if ref in stack:
                raise SpecError(f"Circular local reference: {ref}")
            target: Any = root
            try:
                for part in unquote(ref[2:]).split("/"):
                    part = part.replace("~1", "/").replace("~0", "~")
                    target = target[int(part)] if isinstance(target, list) else target[part]
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                raise SpecError(f"Unresolved local reference: {ref}") from exc
            resolved = self._resolve(target, root, (*stack, ref), depth + 1, schema_context)
            siblings = {key: value for key, value in node.items() if key != "$ref"}
            if siblings and isinstance(resolved, dict):
                siblings = self._resolve(siblings, root, stack, depth + 1, schema_context)
                # Preserve schema constraints; never overwrite a referenced minimum/type.
                if root["openapi"].startswith("3.1") and schema_context:
                    return {"allOf": [resolved, siblings]}
                if root["openapi"].startswith("3.1"):
                    return {**resolved, **{key: value for key, value in siblings.items() if key in {"summary", "description"}}}
                return resolved  # OAS 3.0 reference siblings are ignored.
            return resolved
        result = {}
        for key, value in node.items():
            if key in DATA_FIELDS or key.startswith("x-"):
                result[key] = value
            elif key == "schemas" and isinstance(value, dict):
                result[key] = {name: self._resolve(schema, root, stack, depth + 1, True) for name, schema in value.items()}
            elif schema_context and key in {"properties", "patternProperties", "$defs", "definitions", "dependentSchemas"} and isinstance(value, dict):
                # These are maps of schemas: their property names are literal data,
                # even when a property happens to be called '$ref' or 'example'.
                result[key] = {name: self._resolve(schema, root, stack, depth + 1, True) for name, schema in value.items()}
            else:
                result[key] = self._resolve(value, root, stack, depth + 1, schema_context or key == "schema")
        return result

    def _operation(self, endpoint: str, method: str, item: dict, data: dict, root: dict, version: str) -> Operation:
        params: dict[tuple[str, str], dict] = {}
        unsupported: list[str] = []
        for source in (item.get("parameters", []), data.get("parameters", [])):
            if not isinstance(source, list):
                raise SpecError("parameters must be an array")
            seen: set = set()
            for parameter in source:
                name, location = parameter["name"], parameter["in"]
                if not isinstance(name, str) or location not in {"path", "query", "header", "cookie"}:
                    raise SpecError("Invalid parameter name/location")
                key = (name.lower() if location == "header" else name, location)
                if key in seen:
                    raise SpecError("Duplicate parameter in the same parameter array")
                seen.add(key)
                if "schema" not in parameter:
                    unsupported.append("Parameter content encoding is unsupported")
                if location == "cookie":
                    unsupported.append("Cookie parameters cannot be represented by contract v1.0")
                if location == "path" and parameter.get("required") is not True:
                    raise SpecError("Path parameters must be required")
                if "required" in parameter and not isinstance(parameter["required"], bool):
                    raise SpecError("Parameter required must be a boolean")
                self._check_schema(parameter.get("schema", {}), version)
                params[key] = parameter
        variables = set(re.findall(r"\{([^{}]+)\}", endpoint))
        if variables != {p["name"] for p in params.values() if p["in"] == "path"}:
            raise SpecError("Path template variables and parameter declarations differ")
        body = data.get("requestBody")
        if body is not None:
            if not isinstance(body, dict) or not isinstance(body.get("content"), dict) or not body["content"]:
                raise SpecError("requestBody.content must be a nonempty object")
            if "required" in body and not isinstance(body["required"], bool):
                raise SpecError("requestBody.required must be a boolean")
            if not any(is_json_media(media) for media in body["content"]):
                unsupported.append("Only JSON request bodies are supported")
            for content in body["content"].values():
                self._check_schema(content.get("schema", {}), version)
        responses = data.get("responses")
        if not isinstance(responses, dict) or not responses:
            raise SpecError("Every operation needs documented responses")
        responses = {str(key): value for key, value in responses.items() if not str(key).startswith("x-")}
        for status, response in responses.items():
            if not re.fullmatch(r"[1-5](?:\d{2}|XX)|default", status) or not isinstance(response, dict) or not isinstance(response.get("description"), str):
                raise SpecError("Invalid response status or missing response description")
            for content in response.get("content", {}).values():
                self._check_schema(content.get("schema", {}), version)
        if data.get("security", root.get("security", [])):
            unsupported.append("Security requirements need external authentication/preconditions")
        scenarios = data.get("x-test-scenarios", [])
        if not isinstance(scenarios, list) or any(not isinstance(s, dict) or not isinstance(s.get("request"), dict) or type(s.get("expected_status")) is not int for s in scenarios):
            raise SpecError("x-test-scenarios needs request objects and integer expected_status")
        for scenario in scenarios:
            request = scenario["request"]
            if set(request) - {"path_params", "query_params", "headers", "body"}:
                raise SpecError("Unknown x-test-scenarios request field")
            if any(not isinstance(request.get(k, {}), dict) for k in ("path_params", "query_params", "headers")):
                raise SpecError("Scenario parameter/header containers must be objects")
            if any(not isinstance(v, str) for v in request.get("headers", {}).values()):
                raise SpecError("Scenario header values must be strings")
            if str(scenario["expected_status"]) not in responses:
                raise SpecError("Scenario status must be explicitly documented")
        error_status = data.get("x-validation-error-status")
        if error_status is not None and (type(error_status) is not int or not 400 <= error_status <= 499 or str(error_status) not in responses):
            raise SpecError("x-validation-error-status must be an explicitly documented 4xx integer")
        return Operation(method.upper(), endpoint, list(params.values()), body, responses,
                         data.get("description", data.get("summary", "")), scenarios,
                         error_status, unsupported, version)

    @staticmethod
    def _check_schema(schema: Any, version: str) -> None:
        try:
            Draft202012Validator.check_schema(json_schema(schema, version=version))
        except Exception as exc:
            raise SpecError("Invalid JSON schema in OpenAPI operation") from exc


def is_json_media(media: str) -> bool:
    return media == "application/json" or (media.startswith("application/") and media.endswith("+json"))
