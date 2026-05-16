from __future__ import annotations

import pytest


pytestmark = pytest.mark.observability


def test_every_tool_call_creates_trace_record(
    observed_mcp_client,
    observed_trace_recorder,
) -> None:
    result = observed_mcp_client.call_tool(
        "score_transaction_risk",
        {"transaction_id": "txn_observed_001"},
    )

    assert result.success is True
    assert len(observed_trace_recorder.entries) == 1, (
        "Every MCP tool call must create exactly one trace record."
    )
    record = observed_trace_recorder.entries[0]
    assert record.test_name, "Trace record must capture test_name."
    assert record.workflow_id, "Trace record must capture workflow_id."
    assert record.trace_id == result.metadata.trace_id
    assert record.tool_name == "score_transaction_risk"
    assert record.input_arguments == {"transaction_id": "txn_observed_001"}
    assert record.response_summary["risk_level"] == "LOW"
    assert record.success is True
    assert record.error is None
    assert record.latency_ms is not None and record.latency_ms >= 0
    assert record.timestamp


def test_multi_step_workflows_share_workflow_id(
    observed_mcp_client,
    observed_trace_recorder,
) -> None:
    observed_mcp_client.call_tool("get_transaction", {"transaction_id": "txn_1"})
    observed_mcp_client.call_tool("score_transaction_risk", {"transaction_id": "txn_1"})
    observed_mcp_client.call_tool("create_fraud_case", {"transaction_id": "txn_1"})

    workflow_ids = {entry.workflow_id for entry in observed_trace_recorder.entries}
    assert workflow_ids == {"workflow-observability-001"}, (
        "All trace records produced by one test workflow must share workflow_id."
    )


def test_failed_calls_are_recorded(observed_mcp_client, observed_trace_recorder) -> None:
    result = observed_mcp_client.call_tool("force_failure", {"reason": "test"})

    assert result.success is False
    assert observed_trace_recorder.entries, "Failed tool calls must create trace records."
    record = observed_trace_recorder.entries[-1]
    assert record.tool_name == "force_failure"
    assert record.success is False
    assert record.error and "forced failure" in record.error
    assert record.trace_id
