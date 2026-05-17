from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from fraud_mcp_tests.config import McpTestConfig
from fraud_mcp_tests.mcp_client import McpClient
from fraud_mcp_tests.ragas_eval.adapters import build_investigation_summary_sample
from fraud_mcp_tests.ragas_eval.evaluators import (
    evaluate_investigation_summary,
    write_ragas_report,
)
from tests.workflows.helpers import (
    WorkflowStep,
    call_workflow_tool,
    require_ok,
    string_field,
    summary_text,
    workflow_transaction_id,
)


pytestmark = [pytest.mark.ragas, pytest.mark.llm_eval, pytest.mark.live]

RAGAS_REPORT_PATH = Path("reports/ragas/investigation_summary_ragas.json")


@pytest.fixture
def ragas_live_config(ragas_config: McpTestConfig) -> McpTestConfig:
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is not configured")
    return ragas_config


def test_investigation_summary_ragas_evaluation(
    ragas_live_config: McpTestConfig,
    mcp_client: McpClient,
    transaction_testdata: list[dict[str, Any]],
) -> None:
    transaction_id = workflow_transaction_id(transaction_testdata)
    escalation_reason = "Escalated for optional RAGAS investigation summary evaluation"
    user_input = f"Summarise the fraud investigation for transaction {transaction_id}"
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

    score_step = call_workflow_tool(
        mcp_client,
        steps,
        name="score_transaction_risk",
        tool_name="score_transaction_risk",
        arguments={"transaction_id": transaction_id},
    )
    risk_assessment = require_ok(score_step)

    create_case_step = call_workflow_tool(
        mcp_client,
        steps,
        name="create_fraud_case",
        tool_name="create_fraud_case",
        arguments={"transaction_id": transaction_id},
    )
    case_details = require_ok(create_case_step)
    case_id = string_field(case_details, "case_id")

    escalation_step = call_workflow_tool(
        mcp_client,
        steps,
        name="escalate_case",
        tool_name="escalate_case",
        arguments={"case_id": case_id, "reason": escalation_reason},
    )
    escalation_details = require_ok(escalation_step)

    summary_step = call_workflow_tool(
        mcp_client,
        steps,
        name="generate_investigation_summary",
        tool_name="generate_investigation_summary",
        arguments={"case_id": case_id},
    )
    investigation_summary = require_ok(summary_step)
    response = summary_text(investigation_summary)

    sample = build_investigation_summary_sample(
        user_input=user_input,
        response=response,
        contexts=[
            _context("transaction_details", transaction),
            _context("risk_assessment", risk_assessment),
            _context("case_details", case_details),
            _context("escalation_details", escalation_details),
        ],
        reference=(
            "The summary should stay grounded in the transaction, risk assessment, "
            "case, and escalation evidence returned by the MCP workflow."
        ),
    )

    results = evaluate_investigation_summary(sample, config=ragas_live_config)
    write_ragas_report(results, RAGAS_REPORT_PATH)

    failures = [
        result
        for result in results
        if not result["passed"]
    ]
    assert not failures, (
        "Investigation summary RAGAS scores must meet configured thresholds. "
        f"Failures: {failures}. Full results written to {RAGAS_REPORT_PATH}."
    )


def _context(label: str, payload: dict[str, Any]) -> str:
    return f"{label}: {json.dumps(payload, sort_keys=True, default=str)}"
