from __future__ import annotations

import pytest

from fraud_mcp_tests.mcp_client import McpClient
from tests.workflows.helpers import (
    VALID_CASE_STATUSES,
    WorkflowStep,
    assert_every_step_has_trace,
    assert_safe_failure,
    call_workflow_tool,
    require_ok,
    string_field,
    workflow_transaction_id,
    write_workflow_evidence,
)


pytestmark = [pytest.mark.workflow, pytest.mark.stateful]


def test_state_transition_matrix_is_well_formed(workflow_scenarios) -> None:
    matrix = workflow_scenarios["state_transition_matrix"]

    assert matrix, "Workflow scenario data must define a state transition matrix."
    for transition in matrix:
        assert transition["tool"], f"Transition must identify a tool: {transition}."
        assert isinstance(transition["allowed"], bool), (
            f"Transition allowed flag must be boolean: {transition}."
        )
        if transition["allowed"]:
            assert transition["from_status"] in VALID_CASE_STATUSES, (
                f"Allowed transition has unknown source state: {transition}."
            )
            assert transition["to_status"] in VALID_CASE_STATUSES, (
                f"Allowed transition has unknown target state: {transition}."
            )


@pytest.mark.live
def test_case_can_move_from_created_to_escalated(
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

    case_id, initial_status = _create_case_from_transaction(
        mcp_client,
        steps,
        transaction_id,
    )
    assert initial_status in set(scenario["expected_initial_statuses"]), (
        "New fraud case must start in a valid pre-escalation state. "
        f"Case: {case_id}. Initial status: {initial_status}."
    )

    escalation_step = call_workflow_tool(
        mcp_client,
        steps,
        name="escalate_case",
        tool_name="escalate_case",
        arguments={"case_id": case_id, "reason": scenario["escalation_reason"]},
    )
    escalation = require_ok(escalation_step)
    escalated_status = string_field(escalation, "status").upper()

    assert escalated_status == scenario["expected_escalated_status"], (
        "Fraud case must move from CREATED/open investigation state to ESCALATED. "
        f"Case: {case_id}. Response: {escalation}."
    )

    assert_every_step_has_trace(steps, trace_recorder)
    write_workflow_evidence(
        evidence_writer,
        "workflow_state_created_to_escalated",
        steps,
        trace_recorder,
        {
            "transaction_id": transaction_id,
            "case_id": case_id,
            "initial_status": initial_status,
            "escalated_status": escalated_status,
        },
    )


@pytest.mark.live
def test_case_cannot_be_escalated_without_valid_case_id(
    mcp_client: McpClient,
    workflow_scenarios,
    evidence_writer,
    trace_recorder,
) -> None:
    scenario = _scenario(workflow_scenarios, "invalid_case_escalation")
    steps: list[WorkflowStep] = []

    mcp_client.initialize()
    step = call_workflow_tool(
        mcp_client,
        steps,
        name="escalate_invalid_case",
        tool_name="escalate_case",
        arguments={
            "case_id": scenario["invalid_case_id"],
            "reason": scenario["escalation_reason"],
        },
    )

    assert_safe_failure(step, "Escalating without a valid case_id")
    assert_every_step_has_trace(steps, trace_recorder)
    write_workflow_evidence(
        evidence_writer,
        "workflow_invalid_case_escalation",
        steps,
        trace_recorder,
        {"invalid_case_id": scenario["invalid_case_id"]},
    )


@pytest.mark.live
def test_repeated_escalation_does_not_corrupt_case_state(
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

    case_id, _initial_status = _create_case_from_transaction(
        mcp_client,
        steps,
        transaction_id,
    )
    first = require_ok(
        call_workflow_tool(
            mcp_client,
            steps,
            name="first_escalation",
            tool_name="escalate_case",
            arguments={"case_id": case_id, "reason": scenario["escalation_reason"]},
        )
    )
    second = require_ok(
        call_workflow_tool(
            mcp_client,
            steps,
            name="repeat_escalation",
            tool_name="escalate_case",
            arguments={"case_id": case_id, "reason": scenario["escalation_reason"]},
        )
    )

    first_status = string_field(first, "status").upper()
    second_status = string_field(second, "status").upper()
    assert first_status == "ESCALATED", (
        f"First escalation must move case to ESCALATED. Response: {first}."
    )
    assert second_status == "ESCALATED", (
        "Repeated escalation must not corrupt case state or move it out of "
        f"ESCALATED. Response: {second}."
    )

    assert_every_step_has_trace(steps, trace_recorder)
    write_workflow_evidence(
        evidence_writer,
        "workflow_repeated_escalation",
        steps,
        trace_recorder,
        {
            "transaction_id": transaction_id,
            "case_id": case_id,
            "first_status": first_status,
            "second_status": second_status,
        },
    )


def _create_case_from_transaction(
    mcp_client: McpClient,
    steps: list[WorkflowStep],
    transaction_id: str,
) -> tuple[str, str]:
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
    case_id = string_field(created_case, "case_id")
    initial_case = require_ok(
        call_workflow_tool(
            mcp_client,
            steps,
            name="get_initial_case_status",
            tool_name="get_case_status",
            arguments={"case_id": case_id},
        )
    )
    return case_id, string_field(initial_case, "status").upper()


def _scenario(workflow_scenarios, name: str) -> dict:
    for scenario in workflow_scenarios["scenarios"]:
        if scenario["name"] == name:
            return scenario
    raise AssertionError(f"Missing workflow scenario: {name}")
