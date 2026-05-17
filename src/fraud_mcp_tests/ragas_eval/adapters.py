"""Adapters for building RAGAS-compatible evaluation samples.

These helpers only transform evidence already collected by tests and workflows.
They intentionally do not call the MCP server or import RAGAS directly.
"""

from __future__ import annotations

from typing import TypedDict


class InvestigationSummarySample(TypedDict, total=False):
    user_input: str
    response: str
    contexts: list[str]
    reference: str


class PolicyGroundingSample(TypedDict, total=False):
    user_input: str
    response: str
    contexts: list[str]
    reference: str


class AgentWorkflowSample(TypedDict):
    user_input: str
    expected_tools: list[str]
    actual_tools: list[str]
    response: str


def build_investigation_summary_sample(
    user_input: str,
    response: str,
    contexts: list[str],
    reference: str | None = None,
) -> InvestigationSummarySample:
    """Build a sample for summary faithfulness and factuality evaluation."""

    sample: InvestigationSummarySample = {
        "user_input": user_input,
        "response": response,
        "contexts": list(contexts),
    }
    if reference is not None:
        sample["reference"] = reference
    return sample


def build_policy_grounding_sample(
    user_input: str,
    response: str,
    policy_context: str,
    reference: str | None = None,
) -> PolicyGroundingSample:
    """Build a sample for evaluating response grounding against policy text."""

    sample: PolicyGroundingSample = {
        "user_input": user_input,
        "response": response,
        "contexts": [policy_context],
    }
    if reference is not None:
        sample["reference"] = reference
    return sample


def build_agent_workflow_sample(
    user_input: str,
    expected_tools: list[str],
    actual_tools: list[str],
    final_response: str,
) -> AgentWorkflowSample:
    """Build a sample for agent workflow/tool-use evaluation."""

    return {
        "user_input": user_input,
        "expected_tools": list(expected_tools),
        "actual_tools": list(actual_tools),
        "response": final_response,
    }
