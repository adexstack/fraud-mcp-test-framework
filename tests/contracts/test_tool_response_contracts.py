from __future__ import annotations

from typing import Any

import pytest
from jsonschema import Draft202012Validator

from fraud_mcp_tests.schemas.expected_tools import EXPECTED_TOOLS
from fraud_mcp_tests.schemas.tool_contracts import (
    ERROR_RESPONSE_SCHEMA,
    TOOL_CONTRACTS,
    TOOL_RESPONSE_SCHEMAS,
    ToolContract,
)


pytestmark = pytest.mark.contract

JSON_SCHEMA_TYPES = {"array", "boolean", "integer", "number", "object", "string"}


@pytest.mark.parametrize("contract", TOOL_CONTRACTS.values(), ids=lambda c: c.name)
def test_output_contracts_are_valid_json_schemas(contract: ToolContract) -> None:
    Draft202012Validator.check_schema(contract.output_schema)


@pytest.mark.parametrize("expected_tool", EXPECTED_TOOLS, ids=lambda tool: tool.name)
def test_response_contract_contains_required_fields(expected_tool) -> None:
    schema = TOOL_RESPONSE_SCHEMAS[expected_tool.name]
    required_fields = set(schema.get("required", []))
    expected_fields = set(expected_tool.expected_response_fields)

    assert expected_fields <= required_fields, (
        f"Tool {expected_tool.name} response contract is missing PTB-required "
        f"fields. Missing: {sorted(expected_fields - required_fields)}."
    )

    properties = schema.get("properties", {})
    assert expected_fields <= set(properties), (
        f"Tool {expected_tool.name} response contract must define schemas for all "
        f"required fields. Missing properties: {sorted(expected_fields - set(properties))}."
    )


@pytest.mark.parametrize("contract", TOOL_CONTRACTS.values(), ids=lambda c: c.name)
def test_response_field_types_are_defined_and_valid(contract: ToolContract) -> None:
    properties = contract.output_schema.get("properties", {})

    for field_name in contract.output_schema.get("required", []):
        field_schema = properties.get(field_name)
        assert isinstance(field_schema, dict), (
            f"Tool {contract.name} response field {field_name} must have a schema."
        )
        _assert_json_schema_type_is_valid(contract.name, field_name, field_schema)


@pytest.mark.parametrize("contract", TOOL_CONTRACTS.values(), ids=lambda c: c.name)
def test_error_response_contract_is_consistent(contract: ToolContract) -> None:
    assert contract.error_schema == ERROR_RESPONSE_SCHEMA, (
        f"Tool {contract.name} must use the shared error response contract so "
        "error evidence is consistent across Fraud MCP tools."
    )

    required_fields = set(contract.error_schema.get("required", []))
    assert required_fields == {"error_code", "message", "trace_id", "retryable"}, (
        f"Tool {contract.name} error contract must require error_code, message, "
        f"trace_id, and retryable. Got: {sorted(required_fields)}."
    )

    properties = contract.error_schema.get("properties", {})
    expected_types = {
        "error_code": "string",
        "message": "string",
        "trace_id": "string",
        "retryable": "boolean",
    }
    for field_name, expected_type in expected_types.items():
        actual_type = properties.get(field_name, {}).get("type")
        assert actual_type == expected_type, (
            f"Tool {contract.name} error field {field_name} has invalid type. "
            f"Expected {expected_type!r}, got {actual_type!r}."
        )


def _assert_json_schema_type_is_valid(
    tool_name: str,
    field_name: str,
    field_schema: dict[str, Any],
) -> None:
    field_type = field_schema.get("type")
    if isinstance(field_type, list):
        invalid_types = set(field_type) - JSON_SCHEMA_TYPES
        assert not invalid_types, (
            f"Tool {tool_name} response field {field_name} contains invalid JSON "
            f"Schema types: {sorted(invalid_types)}."
        )
        return

    assert field_type in JSON_SCHEMA_TYPES, (
        f"Tool {tool_name} response field {field_name} must define a valid JSON "
        f"Schema type. Got {field_type!r}."
    )
