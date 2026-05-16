from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from fraud_mcp_tests.config import McpTestConfig
from fraud_mcp_tests.mcp_client import McpClient, ToolCallResult
from fraud_mcp_tests.schemas.expected_tools import EXPECTED_TOOL_NAMES


pytestmark = pytest.mark.invocation


@pytest.mark.live
def test_each_expected_tool_can_be_called_with_minimal_payload(
    mcp_client: McpClient,
    expected_tool_name: str,
    minimal_tool_payloads: Mapping[str, dict[str, object]],
    evidence_writer,
    trace_recorder,
) -> None:
    mcp_client.initialize()
    payload = minimal_tool_payloads[expected_tool_name]

    result = mcp_client.call_tool(expected_tool_name, payload)

    assert isinstance(result, ToolCallResult), (
        f"Tool {expected_tool_name} must return a structured ToolCallResult."
    )
    assert result.tool_name == expected_tool_name, (
        f"ToolCallResult.tool_name must preserve the invoked tool name for "
        f"{expected_tool_name}."
    )
    assert result.arguments == payload, (
        f"ToolCallResult.arguments must preserve the invocation payload for "
        f"{expected_tool_name}."
    )
    assert result.success is True, (
        f"Tool {expected_tool_name} must accept its valid minimal payload. "
        f"Structured error: {result.error}."
    )
    assert isinstance(result.response, dict) and result.response, (
        f"Tool {expected_tool_name} must return a non-empty structured response object."
    )
    assert result.error is None, (
        f"Tool {expected_tool_name} returned an unexpected structured error: "
        f"{result.error}."
    )
    assert isinstance(result.latency_ms, int | float) and result.latency_ms >= 0, (
        f"Tool {expected_tool_name} must capture non-negative latency_ms."
    )
    assert isinstance(result.trace_id, str) and result.trace_id.strip(), (
        f"Tool {expected_tool_name} must capture a server trace_id or generate a "
        "local trace_id."
    )

    evidence_writer.write_json(
        f"tool_invocation_{expected_tool_name}",
        {
            "tool_name": expected_tool_name,
            "arguments": payload,
            "result": _tool_call_result_to_dict(result),
            "trace": trace_recorder.as_dict(),
        },
    )


def test_all_expected_tools_have_minimal_payloads(
    minimal_tool_payloads: Mapping[str, dict[str, object]],
) -> None:
    missing = sorted(set(EXPECTED_TOOL_NAMES) - set(minimal_tool_payloads))
    unexpected = sorted(set(minimal_tool_payloads) - set(EXPECTED_TOOL_NAMES))

    assert not missing, (
        "Invocation test data must include a valid minimal payload for every "
        f"expected tool. Missing: {missing}."
    )
    assert not unexpected, (
        "Invocation test data must not include payloads for unknown tools. "
        f"Unexpected: {unexpected}."
    )


def test_tool_invocation_failures_are_structured(monkeypatch) -> None:
    client = McpClient(
        McpTestConfig(
            server_url="http://mcp.example.test/mcp",
            transport="http",
            timeout_seconds=1,
        )
    )

    def fail_request(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("simulated transport failure")

    monkeypatch.setattr(client, "request", fail_request)

    result = client.call_tool("score_transaction_risk", {"transaction_id": "txn_001"})

    assert isinstance(result, ToolCallResult), (
        "Tool invocation failures must be returned as ToolCallResult objects."
    )
    assert result.success is False, "Failed tool invocations must set success=False."
    assert result.response is None, "Failed tool invocations must not expose raw responses."
    assert result.error == "simulated transport failure", (
        "Failed tool invocations must capture the failure message as structured error text."
    )
    assert isinstance(result.latency_ms, int | float) and result.latency_ms >= 0, (
        "Failed tool invocations must still capture latency_ms."
    )
    assert isinstance(result.trace_id, str) and result.trace_id.strip(), (
        "Failed tool invocations must still capture or generate a trace_id."
    )

    client.close()


def _tool_call_result_to_dict(result: ToolCallResult) -> dict[str, object]:
    return {
        "tool_name": result.tool_name,
        "arguments": result.arguments,
        "success": result.success,
        "response": result.response,
        "error": result.error,
        "latency_ms": result.latency_ms,
        "trace_id": result.trace_id,
        "timestamp": result.timestamp,
    }
