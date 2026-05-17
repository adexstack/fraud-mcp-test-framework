from __future__ import annotations

import httpx
import pytest

from fraud_mcp_tests.config import McpTestConfig
from fraud_mcp_tests.mcp_client import McpClient, ToolCallResult
from fraud_mcp_tests.trace import TraceRecorder


def _config(auth_token: str | None = None) -> McpTestConfig:
    return McpTestConfig(
        server_url="http://mcp.example.test/mcp",
        transport="http",
        auth_token=auth_token,
        timeout_seconds=1,
    )


@pytest.mark.connection
def test_health_check_returns_true_for_reachable_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(200, text="ok")

    client = McpClient(_config(), transport=httpx.MockTransport(handler))

    assert client.health_check() is True
    assert client.metadata[0].method == "health_check"
    assert client.metadata[0].status_code == 200
    assert client.metadata[0].latency_ms >= 0


@pytest.mark.discovery
def test_list_tools_returns_advertised_tools_and_records_trace() -> None:
    trace_recorder = TraceRecorder()

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert b'"method":"tools/list"' in body
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "tools": [
                        {
                            "name": "assess_fraud_risk",
                            "description": "Assess fraud risk",
                            "inputSchema": {"type": "object"},
                        }
                    ]
                },
            },
        )

    client = McpClient(
        _config(),
        trace_recorder=trace_recorder,
        transport=httpx.MockTransport(handler),
    )

    tools = client.list_tools()

    assert tools[0]["name"] == "assess_fraud_risk"
    assert client.metadata[0].method == "tools/list"
    assert trace_recorder.entries[0].method == "tools/list"
    assert trace_recorder.entries[0].trace_id == client.metadata[0].trace_id


@pytest.mark.invocation
def test_call_tool_returns_structured_success_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret-token"
        assert request.headers["x-trace-id"]
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"risk_score": 0.82, "decision": "review"},
            },
        )

    client = McpClient(
        _config(auth_token="secret-token"),
        transport=httpx.MockTransport(handler),
    )

    result = client.call_tool(
        "assess_fraud_risk",
        {"transaction_id": "txn-123", "amount": 250.75},
    )

    assert isinstance(result, ToolCallResult)
    assert result.tool_name == "assess_fraud_risk"
    assert result.arguments == {"transaction_id": "txn-123", "amount": 250.75}
    assert result.success is True
    assert result.response == {"risk_score": 0.82, "decision": "review"}
    assert result.error is None
    assert result.latency_ms >= 0
    assert result.trace_id
    assert result.timestamp
    assert result.metadata is not None
    assert result.metadata.status_code == 200


@pytest.mark.invocation
def test_call_tool_prefers_server_trace_id_when_returned() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"trace_id": "server-trace-123", "decision": "review"},
            },
        )

    client = McpClient(_config(), transport=httpx.MockTransport(handler))

    result = client.call_tool("score_transaction_risk", {"transaction_id": "txn-123"})

    assert result.trace_id == "server-trace-123"
    assert result.metadata is not None
    assert result.metadata.trace_id != result.trace_id


@pytest.mark.invocation
def test_call_tool_returns_structured_error_result_for_mcp_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32602, "message": "Invalid arguments"},
            },
        )

    client = McpClient(_config(), transport=httpx.MockTransport(handler))

    result = client.call_tool("assess_fraud_risk", {"amount": "not-a-number"})

    assert result.success is False
    assert result.response is None
    assert "Invalid arguments" in result.error
    assert result.metadata is not None
    assert result.metadata.error is not None
    assert result.metadata.response == {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32602, "message": "Invalid arguments"},
    }


@pytest.mark.connection
def test_health_check_returns_false_for_network_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = McpClient(_config(), transport=httpx.MockTransport(handler))

    assert client.health_check() is False
    assert client.metadata[0].error == "connection refused"


@pytest.mark.connection
def test_health_check_retries_timeout_before_success() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("server still waking")
        return httpx.Response(200, text="ok")

    client = McpClient(
        McpTestConfig(
            server_url="http://mcp.example.test/mcp",
            transport="http",
            timeout_seconds=1,
            retry_attempts=2,
            retry_backoff_seconds=0,
        ),
        transport=httpx.MockTransport(handler),
    )

    assert client.health_check() is True
    assert attempts == 2
    assert client.metadata[0].attempts == 2


@pytest.mark.connection
def test_request_retries_transient_timeout_before_success() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("server still waking")
        body = request.read()
        assert b'"method":"initialize"' in body
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"serverInfo": {"name": "fraud-mcp"}},
            },
        )

    client = McpClient(
        McpTestConfig(
            server_url="http://mcp.example.test/mcp",
            transport="http",
            timeout_seconds=1,
            retry_attempts=2,
            retry_backoff_seconds=0,
        ),
        transport=httpx.MockTransport(handler),
    )

    assert client.initialize() == {"serverInfo": {"name": "fraud-mcp"}}
    assert attempts == 2
    assert client.metadata[0].attempts == 2
