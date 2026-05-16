from __future__ import annotations

import httpx
import pytest

from fraud_mcp_tests.config import McpTestConfig
from fraud_mcp_tests.mcp_client import McpClient


@pytest.mark.live
def test_mcp_server_is_reachable(mcp_client, evidence_writer, trace_recorder) -> None:
    reachable = mcp_client.health_check()

    assert reachable is True, (
        "MCP server must be reachable at MCP_SERVER_URL before PTB validation can run."
    )

    evidence_writer.write_json(
        "connection_health_check",
        {"reachable": reachable, "trace": trace_recorder.as_dict()},
    )

@pytest.mark.live
def test_mcp_server_initializes(mcp_client, evidence_writer, trace_recorder) -> None:
    result = mcp_client.initialize()

    assert result, "Expected initialize to return server metadata"
    assert "serverInfo" in result or "capabilities" in result, (
        "initialize result should include serverInfo or capabilities"
    )

    evidence_writer.write_json(
        "connection_initialize",
        {"initialize_result": result, "trace": trace_recorder.as_dict()},
    )


@pytest.mark.connection
def test_mcp_server_not_reachable_is_reported_as_false() -> None:
    def unreachable_server(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = McpClient(
        McpTestConfig(
            server_url="http://mcp-unreachable.example.test/mcp",
            transport="http",
            timeout_seconds=1,
        ),
        transport=httpx.MockTransport(unreachable_server),
    )

    try:
        reachable = client.health_check()

        assert reachable is False, (
            "MCP health check must return False when the server is not reachable "
            "or not running."
        )
        assert client.metadata[0].error == "connection refused", (
            "MCP health check must capture the connection failure in metadata."
        )
        assert client.metadata[0].latency_ms >= 0, (
            "MCP health check must capture latency even when the server is unreachable."
        )
    finally:
        client.close()
