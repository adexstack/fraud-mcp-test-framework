from __future__ import annotations

from dataclasses import asdict

import pytest

from fraud_mcp_tests.assertions import (
    assert_all_tools_have_descriptions,
    assert_expected_tools_present,
    assert_tool_names_are_snake_case,
    assert_tool_names_are_unique,
    assert_tools_discovered,
)
from fraud_mcp_tests.schemas.expected_tools import EXPECTED_TOOL_NAMES, EXPECTED_TOOLS


pytestmark = [pytest.mark.discovery, pytest.mark.live]


def test_mcp_tool_discovery(mcp_client, evidence_writer, trace_recorder) -> None:
    mcp_client.initialize()
    tools = mcp_client.list_tools()

    assert_tools_discovered(tools)
    assert_expected_tools_present(tools, EXPECTED_TOOL_NAMES)
    assert_tool_names_are_unique(tools)
    assert_tool_names_are_snake_case(tools)
    assert_all_tools_have_descriptions(tools)

    evidence_writer.write_json(
        "tool_discovery",
        {
            "expected_tools": [asdict(tool) for tool in EXPECTED_TOOLS],
            "discovered_tools": tools,
            "trace": trace_recorder.as_dict(),
        },
    )
