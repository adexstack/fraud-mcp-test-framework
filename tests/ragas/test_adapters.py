from __future__ import annotations

import pytest

from fraud_mcp_tests.ragas_eval.adapters import (
    build_agent_workflow_sample,
    build_investigation_summary_sample,
    build_policy_grounding_sample,
)


pytestmark = [pytest.mark.ragas, pytest.mark.llm_eval]


def test_build_investigation_summary_sample_with_reference() -> None:
    contexts = [
        "Transaction TXN-CRIT-001 amount is 9800 GBP.",
        "Risk score for TXN-CRIT-001 is 92 with velocity and device signals.",
    ]

    sample = build_investigation_summary_sample(
        user_input="Summarise the fraud investigation for TXN-CRIT-001",
        response="TXN-CRIT-001 is high risk due to velocity and device signals.",
        contexts=contexts,
        reference="Mention high risk and cite available transaction evidence.",
    )

    assert sample == {
        "user_input": "Summarise the fraud investigation for TXN-CRIT-001",
        "response": "TXN-CRIT-001 is high risk due to velocity and device signals.",
        "contexts": contexts,
        "reference": "Mention high risk and cite available transaction evidence.",
    }
    assert sample["contexts"] is not contexts


def test_build_investigation_summary_sample_without_reference() -> None:
    sample = build_investigation_summary_sample(
        user_input="Summarise case CASE-001",
        response="CASE-001 requires manual review.",
        contexts=["CASE-001 status is escalated."],
    )

    assert sample == {
        "user_input": "Summarise case CASE-001",
        "response": "CASE-001 requires manual review.",
        "contexts": ["CASE-001 status is escalated."],
    }


def test_build_policy_grounding_sample_wraps_policy_as_context() -> None:
    sample = build_policy_grounding_sample(
        user_input="Can we call this confirmed fraud?",
        response="The evidence indicates elevated risk, not a final legal conclusion.",
        policy_context="Summaries must avoid final legal or criminal conclusions.",
    )

    assert sample == {
        "user_input": "Can we call this confirmed fraud?",
        "response": "The evidence indicates elevated risk, not a final legal conclusion.",
        "contexts": ["Summaries must avoid final legal or criminal conclusions."],
    }


def test_build_policy_grounding_sample_with_reference() -> None:
    sample = build_policy_grounding_sample(
        user_input="Draft an investigation summary.",
        response="Manual review is recommended based on available evidence.",
        policy_context="Use observational language and preserve uncertainty.",
        reference="Use cautious, evidence-grounded wording.",
    )

    assert sample["contexts"] == ["Use observational language and preserve uncertainty."]
    assert sample["reference"] == "Use cautious, evidence-grounded wording."


def test_build_agent_workflow_sample() -> None:
    expected_tools = [
        "get_transaction",
        "score_transaction_risk",
        "create_fraud_case",
        "escalate_case",
        "generate_investigation_summary",
    ]
    actual_tools = [
        "get_transaction",
        "score_transaction_risk",
        "create_fraud_case",
        "generate_investigation_summary",
    ]

    sample = build_agent_workflow_sample(
        user_input="Investigate TXN-CRIT-001",
        expected_tools=expected_tools,
        actual_tools=actual_tools,
        final_response="The transaction was investigated and summarised.",
    )

    assert sample == {
        "user_input": "Investigate TXN-CRIT-001",
        "expected_tools": expected_tools,
        "actual_tools": actual_tools,
        "response": "The transaction was investigated and summarised.",
    }
    assert sample["expected_tools"] is not expected_tools
    assert sample["actual_tools"] is not actual_tools
