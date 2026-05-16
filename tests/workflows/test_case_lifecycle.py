from __future__ import annotations

import pytest

from fraud_mcp_tests.mcp_client import McpClient
from tests.workflows.helpers import (
    VALID_CASE_STATUSES,
    VALID_RISK_LEVELS,
    WorkflowStep,
    assert_every_step_has_trace,
    call_workflow_tool,
    field,
    numeric_field,
    require_ok,
    step_index,
    string_field,
    summary_text,
    workflow_transaction_id,
    write_workflow_evidence,
)


pytestmark = [pytest.mark.workflow, pytest.mark.live]


def test_fraud_case_lifecycle_workflow(
    mcp_client: McpClient,
    transaction_testdata,
    evidence_writer,
    trace_recorder,
) -> None:
    transaction_id = workflow_transaction_id(transaction_testdata)
    escalation_reason = "Escalated by lifecycle workflow validation"
    steps: list[WorkflowStep] = []

    mcp_client.initialize()

    transaction_step = call_workflow_tool(
        mcp_client,
        steps,
        name="get_transaction",
        tool_name="get_transaction",
        arguments={"transaction_id": transaction_id},
    )
    transaction = require_ok(transaction_step)
    assert field(transaction, "transaction_id") == transaction_id, (
        "Workflow transaction must exist before scoring. "
        f"Expected transaction_id {transaction_id}. Response: {transaction}."
    )

    score_step = call_workflow_tool(
        mcp_client,
        steps,
        name="score_transaction_risk",
        tool_name="score_transaction_risk",
        arguments={"transaction_id": transaction_id},
    )
    score = require_ok(score_step)
    risk_score = numeric_field(score, "risk_score", "score")
    risk_level = string_field(score, "risk_level", "level").upper()
    assert 0 <= risk_score <= 100, (
        "Risk score response must be valid and stay within 0-100. "
        f"Response: {score}."
    )
    assert risk_level in VALID_RISK_LEVELS, (
        "Risk score response must include a valid risk level. "
        f"Response: {score}."
    )

    create_case_step = call_workflow_tool(
        mcp_client,
        steps,
        name="create_fraud_case",
        tool_name="create_fraud_case",
        arguments={"transaction_id": transaction_id},
    )
    assert step_index(steps, "score_transaction_risk") < step_index(
        steps,
        "create_fraud_case",
    ), "Fraud case must be created only after transaction scoring completes."
    created_case = require_ok(create_case_step)
    case_id = string_field(created_case, "case_id")

    initial_status_step = call_workflow_tool(
        mcp_client,
        steps,
        name="get_initial_case_status",
        tool_name="get_case_status",
        arguments={"case_id": case_id},
    )
    initial_case = require_ok(initial_status_step)
    initial_status = string_field(initial_case, "status").upper()
    assert initial_status in VALID_CASE_STATUSES, (
        "Initial fraud case status must be valid. "
        f"Case: {case_id}. Response: {initial_case}."
    )

    escalation_step = call_workflow_tool(
        mcp_client,
        steps,
        name="escalate_case",
        tool_name="escalate_case",
        arguments={"case_id": case_id, "reason": escalation_reason},
    )
    escalation = require_ok(escalation_step)
    retained_reason = string_field(escalation, "escalation_reason", "reason")
    assert retained_reason == escalation_reason, (
        "Escalation response must retain the escalation reason. "
        f"Expected {escalation_reason!r}. Response: {escalation}."
    )

    updated_status_step = call_workflow_tool(
        mcp_client,
        steps,
        name="get_updated_case_status",
        tool_name="get_case_status",
        arguments={"case_id": case_id},
    )
    updated_case = require_ok(updated_status_step)
    updated_status = string_field(updated_case, "status").upper()
    assert updated_status in VALID_CASE_STATUSES, (
        "Updated fraud case status must be valid after escalation. "
        f"Case: {case_id}. Response: {updated_case}."
    )
    assert updated_status != initial_status or updated_status == "ESCALATED", (
        "Escalation must change case status or leave the case explicitly ESCALATED. "
        f"Initial status: {initial_status}. Updated status: {updated_status}."
    )

    summary_step = call_workflow_tool(
        mcp_client,
        steps,
        name="generate_investigation_summary",
        tool_name="generate_investigation_summary",
        arguments={"case_id": case_id},
    )
    summary = require_ok(summary_step)
    text = summary_text(summary).lower()
    assert transaction_id.lower() in text, (
        "Investigation summary must reference the transaction_id. "
        f"Transaction: {transaction_id}. Summary: {summary}."
    )
    assert risk_level.lower() in text, (
        "Investigation summary must reference the scored risk level. "
        f"Risk level: {risk_level}. Summary: {summary}."
    )
    assert case_id.lower() in text, (
        "Investigation summary must reference the case_id. "
        f"Case: {case_id}. Summary: {summary}."
    )

    assert_every_step_has_trace(steps, trace_recorder)
    write_workflow_evidence(
        evidence_writer,
        "workflow_case_lifecycle",
        steps,
        trace_recorder,
        {
            "transaction_id": transaction_id,
            "case_id": case_id,
            "risk_level": risk_level,
            "initial_status": initial_status,
            "updated_status": updated_status,
        },
    )
