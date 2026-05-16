from __future__ import annotations

import pytest

from fraud_mcp_tests.mcp_client import McpClient
from tests.workflows.helpers import (
    WorkflowStep,
    assert_every_step_has_trace,
    assert_safe_failure,
    call_workflow_tool,
    require_ok,
    string_field,
    summary_text,
    workflow_transaction_id,
    write_workflow_evidence,
)


pytestmark = [pytest.mark.workflow, pytest.mark.stateful, pytest.mark.live]


def test_case_status_is_consistent_across_repeated_reads(
    mcp_client: McpClient,
    transaction_testdata,
    evidence_writer,
    trace_recorder,
) -> None:
    transaction_id = workflow_transaction_id(transaction_testdata)
    steps: list[WorkflowStep] = []
    case_id = _create_case(mcp_client, steps, transaction_id)

    first_status = require_ok(
        call_workflow_tool(
            mcp_client,
            steps,
            name="first_case_status_read",
            tool_name="get_case_status",
            arguments={"case_id": case_id},
        )
    )
    second_status = require_ok(
        call_workflow_tool(
            mcp_client,
            steps,
            name="second_case_status_read",
            tool_name="get_case_status",
            arguments={"case_id": case_id},
        )
    )

    assert first_status == second_status, (
        "Repeated get_case_status calls must return consistent case state when "
        "no state-changing operation occurs between reads. "
        f"First: {first_status}. Second: {second_status}."
    )

    assert_every_step_has_trace(steps, trace_recorder)
    write_workflow_evidence(
        evidence_writer,
        "workflow_repeated_status_consistency",
        steps,
        trace_recorder,
        {"transaction_id": transaction_id, "case_id": case_id},
    )


def test_investigation_summary_reflects_latest_state(
    mcp_client: McpClient,
    transaction_testdata,
    workflow_scenarios,
    evidence_writer,
    trace_recorder,
) -> None:
    scenario = _scenario(workflow_scenarios, "created_to_escalated")
    transaction_id = scenario.get("transaction_id") or workflow_transaction_id(
        transaction_testdata
    )
    steps: list[WorkflowStep] = []
    case_id = _create_case(mcp_client, steps, transaction_id)

    escalation = require_ok(
        call_workflow_tool(
            mcp_client,
            steps,
            name="escalate_case",
            tool_name="escalate_case",
            arguments={"case_id": case_id, "reason": scenario["escalation_reason"]},
        )
    )
    escalated_status = string_field(escalation, "status").upper()
    summary = require_ok(
        call_workflow_tool(
            mcp_client,
            steps,
            name="generate_investigation_summary",
            tool_name="generate_investigation_summary",
            arguments={"case_id": case_id},
        )
    )

    text = summary_text(summary).lower()
    assert case_id.lower() in text, (
        "Investigation summary must reference the current case_id. "
        f"Case: {case_id}. Summary: {summary}."
    )
    assert escalated_status.lower() in text, (
        "Investigation summary must reflect the latest case status. "
        f"Expected status: {escalated_status}. Summary: {summary}."
    )
    assert scenario["escalation_reason"].lower() in text, (
        "Investigation summary must reflect the latest escalation reason. "
        f"Expected reason: {scenario['escalation_reason']!r}. Summary: {summary}."
    )

    assert_every_step_has_trace(steps, trace_recorder)
    write_workflow_evidence(
        evidence_writer,
        "workflow_summary_latest_state",
        steps,
        trace_recorder,
        {
            "transaction_id": transaction_id,
            "case_id": case_id,
            "latest_status": escalated_status,
        },
    )


def test_tool_calls_in_wrong_order_are_handled_safely(
    mcp_client: McpClient,
    workflow_scenarios,
    evidence_writer,
    trace_recorder,
) -> None:
    scenario = _scenario(workflow_scenarios, "wrong_order_summary_without_case")
    steps: list[WorkflowStep] = []

    mcp_client.initialize()
    summary_without_case = call_workflow_tool(
        mcp_client,
        steps,
        name="summary_without_case",
        tool_name="generate_investigation_summary",
        arguments={"case_id": scenario["invalid_case_id"]},
    )
    escalation_without_case = call_workflow_tool(
        mcp_client,
        steps,
        name="escalation_without_case",
        tool_name="escalate_case",
        arguments={
            "case_id": scenario["invalid_case_id"],
            "reason": "Wrong-order workflow validation",
        },
    )

    assert_safe_failure(
        summary_without_case,
        "Generating an investigation summary before case creation",
    )
    assert_safe_failure(
        escalation_without_case,
        "Escalating before case creation",
    )

    assert_every_step_has_trace(steps, trace_recorder)
    write_workflow_evidence(
        evidence_writer,
        "workflow_wrong_order_safety",
        steps,
        trace_recorder,
        {"invalid_case_id": scenario["invalid_case_id"]},
    )


def _create_case(
    mcp_client: McpClient,
    steps: list[WorkflowStep],
    transaction_id: str,
) -> str:
    mcp_client.initialize()
    require_ok(
        call_workflow_tool(
            mcp_client,
            steps,
            name="get_transaction",
            tool_name="get_transaction",
            arguments={"transaction_id": transaction_id},
        )
    )
    require_ok(
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
    return string_field(created_case, "case_id")


def _scenario(workflow_scenarios, name: str) -> dict:
    for scenario in workflow_scenarios["scenarios"]:
        if scenario["name"] == name:
            return scenario
    raise AssertionError(f"Missing workflow scenario: {name}")
