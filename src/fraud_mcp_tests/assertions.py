"""Reusable assertions for MCP black-box tests."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from jsonschema import Draft202012Validator


def assert_tools_discovered(tools: Sequence[Mapping[str, Any]]) -> None:
    assert tools, "Expected the MCP server to advertise at least one tool"
    for tool in tools:
        assert isinstance(tool.get("name"), str) and tool["name"], (
            f"Tool entry must include a non-empty name: {tool!r}"
        )
        assert_tool_has_description(tool)


def assert_expected_tools_present(
    discovered_tools: Sequence[Mapping[str, Any]],
    expected_tool_names: Sequence[str],
) -> None:
    discovered_names = {
        name for tool in discovered_tools if isinstance((name := tool.get("name")), str)
    }
    missing = sorted(set(expected_tool_names) - discovered_names)
    assert not missing, f"Missing expected MCP tools: {missing}"


def assert_tool_names_are_unique(tools: Sequence[Mapping[str, Any]]) -> None:
    names = [name for tool in tools if isinstance((name := tool.get("name")), str)]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, f"Duplicate MCP tool names discovered: {duplicates}"


def assert_tool_names_are_snake_case(tools: Sequence[Mapping[str, Any]]) -> None:
    snake_case = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    invalid = [
        tool.get("name")
        for tool in tools
        if not isinstance(tool.get("name"), str)
        or not snake_case.fullmatch(tool["name"])
    ]
    assert not invalid, f"MCP tool names must be snake_case: {invalid}"


def assert_tool_has_description(tool: Mapping[str, Any]) -> None:
    description = tool.get("description")
    assert isinstance(description, str) and description.strip(), (
        f"Tool {tool.get('name')!r} must include a non-empty description"
    )


def assert_all_tools_have_descriptions(tools: Sequence[Mapping[str, Any]]) -> None:
    for tool in tools:
        assert_tool_has_description(tool)


def assert_tool_has_valid_input_schema(tool: Mapping[str, Any]) -> None:
    schema = tool.get("inputSchema")
    assert isinstance(schema, dict), (
        f"Tool {tool.get('name')!r} must advertise inputSchema as an object"
    )
    Draft202012Validator.check_schema(schema)


def assert_response_matches_schema(
    response: Mapping[str, Any],
    schema: Mapping[str, Any],
    context: str,
) -> None:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(response),
        key=lambda error: list(error.path),
    )
    assert not errors, f"{context} response schema mismatch: {errors[0].message}"
