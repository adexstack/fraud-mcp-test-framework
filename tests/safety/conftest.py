from __future__ import annotations

from typing import Any

import pytest

from fraud_mcp_tests.mcp_client import McpClient
from tests.workflows.helpers import (
    WorkflowStep,
    call_workflow_tool,
    field,
    numeric_field,
    require_ok,
    string_field,
    summary_text,
    workflow_transaction_id,
    write_workflow_evidence,
)


@pytest.fixture
def escalated_case_summary(
    mcp_client: McpClient,
    transaction_testdata,
    workflow_scenarios,
    evidence_writer,
    trace_recorder,
) -> dict[str, Any]:
    scenario = _scenario(workflow_scenarios, "created_to_escalated")
    transaction_id = scenario.get("transaction_id") or workflow_transaction_id(
        transaction_testdata
    )
    steps: list[WorkflowStep] = []

    mcp_client.initialize()
    transaction = require_ok(
        call_workflow_tool(
            mcp_client,
            steps,
            name="get_transaction",
            tool_name="get_transaction",
            arguments={"transaction_id": transaction_id},
        )
    )
    score = require_ok(
        call_workflow_tool(
            mcp_client,
            steps,
            name="score_transaction_risk",
            tool_name="score_transaction_risk",
            arguments={"transaction_id": transaction_id},
        )
    )
    created_case = require_ok(
        call_workflow_tool(
            mcp_client,
            steps,
            name="create_fraud_case",
            tool_name="create_fraud_case",
            arguments={"transaction_id": transaction_id},
        )
    )
    case_id = string_field(created_case, "case_id")
    escalation = require_ok(
        call_workflow_tool(
            mcp_client,
            steps,
            name="escalate_case",
            tool_name="escalate_case",
            arguments={"case_id": case_id, "reason": scenario["escalation_reason"]},
        )
    )
    summary = require_ok(
        call_workflow_tool(
            mcp_client,
            steps,
            name="generate_investigation_summary",
            tool_name="generate_investigation_summary",
            arguments={"case_id": case_id},
        )
    )

    result = {
        "case_id": case_id,
        "transaction_id": transaction_id,
        "customer_id": field(transaction, "customer_id"),
        "risk_score": numeric_field(score, "risk_score", "score"),
        "risk_level": string_field(score, "risk_level", "level").upper(),
        "signals": _signals(score),
        "case_status": string_field(escalation, "status").upper(),
        "escalation_reason": scenario["escalation_reason"],
        "summary": summary,
        "summary_text": summary_text(summary),
        "steps": steps,
    }
    write_workflow_evidence(
        evidence_writer,
        "safety_escalated_case_summary",
        steps,
        trace_recorder,
        {
            "case_id": case_id,
            "transaction_id": transaction_id,
            "risk_level": result["risk_level"],
            "case_status": result["case_status"],
        },
    )
    return result


@pytest.fixture
def incomplete_evidence_summary(
    mcp_client: McpClient,
    workflow_scenarios,
    evidence_writer,
    trace_recorder,
) -> dict[str, Any]:
    scenario = _scenario(workflow_scenarios, "wrong_order_summary_without_case")
    steps: list[WorkflowStep] = []

    mcp_client.initialize()
    step = call_workflow_tool(
        mcp_client,
        steps,
        name="summary_for_missing_case",
        tool_name="generate_investigation_summary",
        arguments={"case_id": scenario["invalid_case_id"]},
    )
    write_workflow_evidence(
        evidence_writer,
        "safety_incomplete_evidence_summary",
        steps,
        trace_recorder,
        {"case_id": scenario["invalid_case_id"]},
    )
    return {
        "case_id": scenario["invalid_case_id"],
        "structured_content": step.structured_content,
        "summary_text": str(step.structured_content),
        "steps": steps,
    }


def normalized(text: str) -> str:
    return " ".join(text.lower().split())


def contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    lowered = normalized(text)
    return any(phrase.lower() in lowered for phrase in phrases)


def _signals(score: dict[str, Any]) -> list[str]:
    signals = field(score, "signals")
    if not isinstance(signals, list):
        return []
    names: list[str] = []
    for signal in signals:
        if isinstance(signal, str):
            names.append(signal)
        elif isinstance(signal, dict):
            name = signal.get("name") or signal.get("code") or signal.get("signal")
            if isinstance(name, str):
                names.append(name)
    return names


def _scenario(workflow_scenarios, name: str) -> dict[str, Any]:
    for scenario in workflow_scenarios["scenarios"]:
        if scenario["name"] == name:
            return scenario
    raise AssertionError(f"Missing workflow scenario: {name}")
