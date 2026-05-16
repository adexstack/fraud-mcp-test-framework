from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from fraud_mcp_tests.config import McpTestConfig
from fraud_mcp_tests.mcp_client import McpClient
from fraud_mcp_tests.trace import TraceRecorder


@pytest.fixture
def observed_trace_recorder() -> TraceRecorder:
    return TraceRecorder(
        test_name="tests/observability/mock_observability_test.py::test_case",
        workflow_id="workflow-observability-001",
    )


@pytest.fixture
def observed_mcp_client(observed_trace_recorder: TraceRecorder) -> McpClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        method = body["method"]
        if method == "tools/call":
            return _tool_call_response(body)
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": body["id"], "result": {"ok": True}},
        )

    client = McpClient(
        McpTestConfig(
            server_url="http://mcp.example.test/mcp",
            transport="http",
            auth_token="super-secret-token",
            timeout_seconds=2,
        ),
        trace_recorder=observed_trace_recorder,
        transport=httpx.MockTransport(handler),
    )
    yield client
    client.close()


def _tool_call_response(body: dict[str, Any]) -> httpx.Response:
    params = body["params"]
    tool_name = params["name"]
    arguments = params.get("arguments", {})
    if tool_name == "force_failure":
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "error": {
                    "code": -32000,
                    "message": "forced failure for observability",
                },
            },
        )

    structured_content = {
        "ok": True,
        "tool_name": tool_name,
        "transaction_id": arguments.get("transaction_id", "txn_observed_001"),
        "risk_level": "LOW",
        "risk_score": 12,
    }
    return httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": body["id"],
            "result": {
                "structuredContent": structured_content,
                "content": [{"type": "text", "text": json.dumps(structured_content)}],
            },
        },
    )
