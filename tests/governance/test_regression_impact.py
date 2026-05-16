from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pytest

from fraud_mcp_tests.baseline import compare_or_update_baseline
from fraud_mcp_tests.mcp_client import McpClient
from fraud_mcp_tests.schemas.expected_tools import EXPECTED_TOOLS
from fraud_mcp_tests.schemas.tool_contracts import TOOL_CONTRACTS
from tests.workflows.helpers import field


pytestmark = [pytest.mark.governance, pytest.mark.regression]


def test_static_regression_baseline_for_tool_contracts() -> None:
    snapshot = {
        "expected_tool_inventory": [asdict(tool) for tool in EXPECTED_TOOLS],
        "tool_schema_contracts": {
            name: {
                "input_required": contract.input_schema.get("required", []),
                "input_properties": _property_types(contract.input_schema),
                "output_required": contract.output_schema.get("required", []),
                "output_properties": _property_types(contract.output_schema),
            }
            for name, contract in sorted(TOOL_CONTRACTS.items())
        },
    }

    comparison = compare_or_update_baseline("static_tool_contracts", snapshot)

    assert not comparison.differences, (
        "Static regression baseline changed. This may indicate an expected tool "
        "disappeared or a required schema field changed. Differences: "
        f"{comparison.differences}."
    )


@pytest.mark.live
def test_live_regression_baseline_for_mcp_behaviour(
    mcp_client: McpClient,
    transaction_testdata,
    workflow_scenarios,
    mcp_config,
) -> None:
    mcp_client.initialize()
    snapshot = {
        "tool_inventory": _live_tool_inventory(mcp_client),
        "known_risk_outcomes": _known_risk_outcomes(mcp_client, transaction_testdata),
        "known_workflow_outcomes": _known_workflow_outcomes(
            mcp_client,
            workflow_scenarios,
        ),
        "latency_threshold_ms": mcp_config.timeout_seconds * 1000,
        "latency_policy": {
            "threshold_ms": mcp_config.timeout_seconds * 1000,
        },
    }

    _assert_latency_within_threshold(mcp_client, mcp_config.timeout_seconds * 1000)
    comparison = compare_or_update_baseline("live_mcp_behaviour", snapshot)

    assert not comparison.differences, (
        "Live MCP regression baseline changed. This may indicate a tool disappeared, "
        "a known risk scenario changed unexpectedly, a workflow state transition "
        "changed, or latency exceeded governance expectations. Differences: "
        f"{comparison.differences}."
    )


def _live_tool_inventory(mcp_client: McpClient) -> list[dict[str, Any]]:
    tools = mcp_client.list_tools()
    return [
        {
            "name": tool.get("name"),
            "description": tool.get("description"),
            "input_required": tool.get("inputSchema", {}).get("required", []),
            "input_properties": _property_types(tool.get("inputSchema", {})),
        }
        for tool in sorted(tools, key=lambda item: item.get("name", ""))
    ]


def _known_risk_outcomes(
    mcp_client: McpClient,
    transaction_testdata: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    outcomes: dict[str, dict[str, Any]] = {}
    for transaction in transaction_testdata:
        result = mcp_client.call_tool(
            "score_transaction_risk",
            {"transaction_id": transaction["transaction_id"]},
        )
        content = _structured_content(result.response)
        if content.get("ok") is False:
            outcomes[transaction["scenario"]] = {
                "status": "unavailable",
                "error": content.get("error"),
            }
            continue
        outcomes[transaction["scenario"]] = {
            "status": "available",
            "transaction_id": field(content, "transaction_id"),
            "risk_level": field(content, "risk_level", "level"),
            "risk_score": field(content, "risk_score", "score"),
            "recommended_action": field(content, "recommended_action", "action"),
        }
    return outcomes


def _known_workflow_outcomes(
    mcp_client: McpClient,
    workflow_scenarios: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    scenario = _scenario(workflow_scenarios, "created_to_escalated")
    transaction_id = scenario["transaction_id"]

    transaction = _structured_content(
        mcp_client.call_tool(
            "get_transaction",
            {"transaction_id": transaction_id},
        ).response
    )
    if transaction.get("ok") is False:
        return {
            "created_to_escalated": {
                "status": "unavailable",
                "error": transaction.get("error"),
            }
        }

    score = _structured_content(
        mcp_client.call_tool(
            "score_transaction_risk",
            {"transaction_id": transaction_id},
        ).response
    )
    created_case = _structured_content(
        mcp_client.call_tool(
            "create_fraud_case",
            {"transaction_id": transaction_id},
        ).response
    )
    case_id = field(created_case, "case_id")
    initial_case = _structured_content(
        mcp_client.call_tool("get_case_status", {"case_id": case_id}).response
    )
    escalated = _structured_content(
        mcp_client.call_tool(
            "escalate_case",
            {"case_id": case_id, "reason": scenario["escalation_reason"]},
        ).response
    )
    return {
        "created_to_escalated": {
            "status": "available",
            "transaction_id": transaction_id,
            "case_id_present": isinstance(case_id, str) and bool(case_id),
            "risk_level": field(score, "risk_level", "level"),
            "initial_status": field(initial_case, "status"),
            "escalated_status": field(escalated, "status"),
        }
    }


def _structured_content(response: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(response, dict):
        return {}
    structured = response.get("structuredContent", response)
    return structured if isinstance(structured, dict) else {}


def _property_types(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return {}
    return {
        name: value.get("type")
        for name, value in sorted(properties.items())
        if isinstance(value, dict)
    }


def _scenario(workflow_scenarios: dict[str, Any], name: str) -> dict[str, Any]:
    for scenario in workflow_scenarios["scenarios"]:
        if scenario["name"] == name:
            return scenario
    raise AssertionError(f"Missing workflow scenario: {name}")


def _assert_latency_within_threshold(
    mcp_client: McpClient,
    threshold: float,
) -> None:
    if not mcp_client._trace_recorder:
        return
    violations = {
        entry.method or entry.tool_name: entry.latency_ms
        for entry in mcp_client._trace_recorder.entries
        if entry.latency_ms is not None and entry.latency_ms > threshold
    }
    assert not violations, (
        "Observed MCP latency exceeded configured threshold. "
        f"Threshold: {threshold} ms. Violations: {violations}."
    )
