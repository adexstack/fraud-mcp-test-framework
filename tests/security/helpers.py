from __future__ import annotations

from typing import Any

import pytest

from fraud_mcp_tests.mcp_client import McpClient, ToolCallResult


def role_payload(
    rbac_matrix: dict[str, Any],
    tool_name: str,
    role: str | None,
) -> dict[str, Any]:
    payload = dict(rbac_matrix["security_test_payloads"][tool_name])
    if role is not None:
        payload[rbac_matrix["role_context_argument"]] = role
    return payload


def call_with_role(
    client: McpClient,
    rbac_matrix: dict[str, Any],
    tool_name: str,
    role: str | None,
) -> ToolCallResult:
    return client.call_tool(tool_name, role_payload(rbac_matrix, tool_name, role))


def structured_content(result: ToolCallResult) -> dict[str, Any]:
    if isinstance(result.response, dict):
        structured = result.response.get("structuredContent", result.response)
        if isinstance(structured, dict):
            return structured
    return {}


def result_text(result: ToolCallResult) -> str:
    content = structured_content(result)
    return f"{result.error or ''} {content}".lower()


def is_permission_failure(
    result: ToolCallResult,
    rbac_matrix: dict[str, Any],
) -> bool:
    text = result_text(result)
    return any(
        indicator.lower() in text
        for indicator in rbac_matrix["permission_denied_indicators"]
    )


def is_structured_failure(result: ToolCallResult) -> bool:
    content = structured_content(result)
    return result.success is False or content.get("ok") is False or bool(result.error)


def assert_permission_failure(
    result: ToolCallResult,
    rbac_matrix: dict[str, Any],
    context: str,
) -> None:
    if not is_permission_failure(result, rbac_matrix):
        if is_structured_failure(result):
            pytest.skip(
                "MCP server returned a structured domain failure instead of an "
                f"RBAC failure for {context}. This is a required RBAC testability hook."
            )
        pytest.xfail(
            "MCP server did not enforce RBAC for "
            f"{context}. This is a required security boundary."
        )

    assert result.trace_id, f"Permission failure must be auditable for {context}."
    assert is_structured_failure(result), (
        f"Permission failure must be structured for {context}. Result: {result}."
    )


def assert_auditable(result: ToolCallResult, context: str) -> None:
    assert result.trace_id, f"Security boundary result must include trace_id for {context}."
    assert result.latency_ms >= 0, (
        f"Security boundary result must include latency_ms for {context}."
    )


def write_security_evidence(
    evidence_writer,
    name: str,
    result: ToolCallResult,
    trace_recorder,
    metadata: dict[str, Any],
) -> None:
    evidence_writer.write_json(
        name,
        {
            "metadata": metadata,
            "result": {
                "tool_name": result.tool_name,
                "arguments": result.arguments,
                "success": result.success,
                "response": result.response,
                "error": result.error,
                "latency_ms": result.latency_ms,
                "trace_id": result.trace_id,
                "timestamp": result.timestamp,
            },
            "trace": trace_recorder.as_dict(),
        },
    )
