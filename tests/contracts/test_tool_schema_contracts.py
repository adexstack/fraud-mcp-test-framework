from __future__ import annotations

from typing import Any

import pytest
from jsonschema import Draft202012Validator

from fraud_mcp_tests.schemas.expected_tools import EXPECTED_TOOL_NAMES
from fraud_mcp_tests.schemas.tool_contracts import TOOL_CONTRACTS, ToolContract


pytestmark = pytest.mark.contract


def test_every_expected_tool_has_schema_contract() -> None:
    contract_names = set(TOOL_CONTRACTS)
    expected_names = set(EXPECTED_TOOL_NAMES)

    assert contract_names == expected_names, (
        "PTB schema evidence requires one input/output contract per expected tool. "
        f"Missing contracts: {sorted(expected_names - contract_names)}. "
        f"Unexpected contracts: {sorted(contract_names - expected_names)}."
    )


@pytest.mark.parametrize("contract", TOOL_CONTRACTS.values(), ids=lambda c: c.name)
def test_input_contracts_are_valid_json_schemas(contract: ToolContract) -> None:
    Draft202012Validator.check_schema(contract.input_schema)


@pytest.mark.live
def test_discovered_tool_input_schemas_match_expected_contracts(mcp_client) -> None:
    mcp_client.initialize()
    discovered_tools = {tool["name"]: tool for tool in mcp_client.list_tools()}

    for tool_name, contract in TOOL_CONTRACTS.items():
        assert tool_name in discovered_tools, (
            "PTB schema evidence requires every expected tool to be discoverable. "
            f"Missing required tool: {tool_name}."
        )
        advertised_schema = discovered_tools[tool_name].get("inputSchema")
        assert isinstance(advertised_schema, dict), (
            f"Tool {tool_name} must advertise inputSchema as an object."
        )
        _assert_input_schema_matches_contract(tool_name, advertised_schema, contract)


def _assert_input_schema_matches_contract(
    tool_name: str,
    advertised_schema: dict[str, Any],
    contract: ToolContract,
) -> None:
    expected_schema = contract.input_schema
    expected_required = set(expected_schema.get("required", []))
    advertised_required = set(advertised_schema.get("required", []))

    assert expected_required <= advertised_required, (
        f"Tool {tool_name} is missing required arguments in advertised schema. "
        f"Expected at least {sorted(expected_required)}, "
        f"got {sorted(advertised_required)}."
    )

    expected_properties = expected_schema.get("properties", {})
    advertised_properties = advertised_schema.get("properties", {})
    assert isinstance(advertised_properties, dict), (
        f"Tool {tool_name} inputSchema.properties must be an object."
    )

    expected_arguments = set(expected_properties)
    advertised_arguments = set(advertised_properties)
    assert advertised_arguments == expected_arguments, (
        f"Tool {tool_name} argument names do not match the expected contract. "
        f"Missing: {sorted(expected_arguments - advertised_arguments)}. "
        f"Unexpected: {sorted(advertised_arguments - expected_arguments)}."
    )

    for argument_name, expected_argument_schema in expected_properties.items():
        advertised_argument_schema = advertised_properties[argument_name]
        expected_type = expected_argument_schema.get("type")
        advertised_type = advertised_argument_schema.get("type")
        assert advertised_type == expected_type, (
            f"Tool {tool_name} argument {argument_name} has the wrong type. "
            f"Expected {expected_type!r}, got {advertised_type!r}."
        )
