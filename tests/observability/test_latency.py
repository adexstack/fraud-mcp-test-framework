from __future__ import annotations

import pytest


pytestmark = pytest.mark.observability


def test_latency_is_captured(observed_mcp_client, observed_trace_recorder) -> None:
    result = observed_mcp_client.call_tool(
        "score_transaction_risk",
        {"transaction_id": "txn_observed_001"},
    )

    assert result.latency_ms >= 0, "ToolCallResult must capture latency_ms."
    assert observed_trace_recorder.entries[-1].latency_ms is not None
    assert observed_trace_recorder.entries[-1].latency_ms >= 0


def test_latency_does_not_exceed_configured_threshold(
    observed_mcp_client,
    observed_trace_recorder,
) -> None:
    observed_mcp_client.call_tool(
        "score_transaction_risk",
        {"transaction_id": "txn_observed_001"},
    )
    record = observed_trace_recorder.entries[-1]
    threshold_ms = observed_mcp_client._config.timeout_seconds * 1000

    assert record.latency_ms is not None
    assert record.latency_ms <= threshold_ms, (
        "Tool call latency must not exceed configured MCP timeout threshold. "
        f"Latency: {record.latency_ms} ms. Threshold: {threshold_ms} ms."
    )
