from __future__ import annotations

import importlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from fraud_mcp_tests.config import McpTestConfig
from fraud_mcp_tests.mcp_client import McpClient
from fraud_mcp_tests.ragas_eval.adapters import build_agent_workflow_sample
from tests.workflows.helpers import (
    WorkflowStep,
    call_workflow_tool,
    require_ok,
    string_field,
    summary_text,
    workflow_transaction_id,
)


pytestmark = [
    pytest.mark.ragas,
    pytest.mark.llm_eval,
    pytest.mark.workflow,
    pytest.mark.live,
]

EXPECTED_TOOL_SEQUENCE = [
    "get_transaction",
    "score_transaction_risk",
    "create_fraud_case",
    "escalate_case",
    "generate_investigation_summary",
]
RAGAS_REPORT_PATH = Path("reports/ragas/agent_workflow_eval.json")
RAGAS_AGENT_METRIC_CANDIDATES = (
    "ToolCallAccuracy",
    "tool_call_accuracy",
    "AgentGoalAccuracy",
    "agent_goal_accuracy",
)


@pytest.fixture
def ragas_live_config(ragas_config: McpTestConfig) -> McpTestConfig:
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is not configured")
    return ragas_config


def test_agent_workflow_ragas_evaluation(
    ragas_live_config: McpTestConfig,
    mcp_client: McpClient,
    transaction_testdata: list[dict[str, Any]],
    trace_recorder,
) -> None:
    transaction_id = workflow_transaction_id(transaction_testdata)
    escalation_reason = "Escalated for optional RAGAS agent workflow evaluation"
    user_input = f"Investigate transaction {transaction_id} and produce a summary."
    steps: list[WorkflowStep] = []

    mcp_client.initialize()

    transaction_step = call_workflow_tool(
        mcp_client,
        steps,
        name="get_transaction",
        tool_name="get_transaction",
        arguments={"transaction_id": transaction_id},
    )
    require_ok(transaction_step)

    score_step = call_workflow_tool(
        mcp_client,
        steps,
        name="score_transaction_risk",
        tool_name="score_transaction_risk",
        arguments={"transaction_id": transaction_id},
    )
    require_ok(score_step)

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
    require_ok(escalation_step)

    summary_step = call_workflow_tool(
        mcp_client,
        steps,
        name="generate_investigation_summary",
        tool_name="generate_investigation_summary",
        arguments={"case_id": case_id},
    )
    summary = require_ok(summary_step)
    final_response = summary_text(summary)

    actual_tools = _actual_tools_from_trace(trace_recorder) or [
        step.tool_name for step in steps
    ]
    sample = build_agent_workflow_sample(
        user_input=user_input,
        expected_tools=EXPECTED_TOOL_SEQUENCE,
        actual_tools=actual_tools,
        final_response=final_response,
    )
    deterministic_metrics = _deterministic_workflow_metrics(
        expected_tools=EXPECTED_TOOL_SEQUENCE,
        actual_tools=actual_tools,
        threshold=ragas_live_config.agent_tool_call_f1_threshold,
    )
    ragas_agent_metrics = _try_ragas_agent_metrics(sample)

    report = {
        "metric_source": (
            "ragas_agent_metric"
            if ragas_agent_metrics["used"]
            else "deterministic_local_fallback"
        ),
        "deterministic_local_fallback": {
            "description": (
                "Lightweight agentic workflow metric comparing expected and "
                "actual MCP tool-call sequences from trace capture."
            ),
            **deterministic_metrics,
        },
        "ragas_agent_metrics": ragas_agent_metrics,
        "sample": sample,
        "trace": trace_recorder.as_dict(),
    }
    RAGAS_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAGAS_REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

    assert deterministic_metrics["exact_sequence_match"], (
        "Agent workflow must follow the expected MCP investigation path. "
        f"Expected: {EXPECTED_TOOL_SEQUENCE}. Actual: {actual_tools}. "
        f"Report written to {RAGAS_REPORT_PATH}."
    )
    assert (
        deterministic_metrics["tool_call_f1"]
        >= ragas_live_config.agent_tool_call_f1_threshold
    ), (
        "Agent workflow tool-call F1 must meet the configured threshold. "
        f"Metrics: {deterministic_metrics}. Report written to {RAGAS_REPORT_PATH}."
    )


def _actual_tools_from_trace(trace_recorder) -> list[str]:
    return [
        entry.tool_name
        for entry in trace_recorder.entries
        if entry.method == "tools/call"
    ]


def _deterministic_workflow_metrics(
    expected_tools: list[str],
    actual_tools: list[str],
    threshold: float,
) -> dict[str, Any]:
    expected_counts = Counter(expected_tools)
    actual_counts = Counter(actual_tools)
    matched = sum((expected_counts & actual_counts).values())
    precision = matched / len(actual_tools) if actual_tools else 0.0
    recall = matched / len(expected_tools) if expected_tools else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    return {
        "metric_name": "agent_tool_call_f1",
        "exact_sequence_match": actual_tools == expected_tools,
        "tool_call_precision": precision,
        "tool_call_recall": recall,
        "tool_call_f1": f1,
        "threshold": threshold,
        "passed": actual_tools == expected_tools and f1 >= threshold,
        "missing_tools": list((expected_counts - actual_counts).elements()),
        "unexpected_tools": list((actual_counts - expected_counts).elements()),
    }


def _try_ragas_agent_metrics(sample: dict[str, Any]) -> dict[str, Any]:
    try:
        metrics_module = importlib.import_module("ragas.metrics")
    except ImportError:
        return {
            "used": False,
            "reason": "RAGAS is not installed; used deterministic local fallback.",
            "available_metrics": [],
        }

    metric_objects: list[Any] = []
    available_metric_names: list[str] = []
    for candidate_name in RAGAS_AGENT_METRIC_CANDIDATES:
        if not hasattr(metrics_module, candidate_name):
            continue
        metric = getattr(metrics_module, candidate_name)
        try:
            metric_objects.append(metric() if isinstance(metric, type) else metric)
        except TypeError:
            continue
        available_metric_names.append(candidate_name)

    if not metric_objects:
        return {
            "used": False,
            "reason": (
                "Installed RAGAS version does not expose supported agent/tool "
                "workflow metrics; used deterministic local fallback."
            ),
            "available_metrics": [],
        }

    try:
        ragas_scores = _evaluate_with_ragas_agent_metrics(sample, metric_objects)
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        return {
            "used": False,
            "reason": (
                "Installed RAGAS agent/tool metrics could not evaluate this "
                f"sample shape; used deterministic local fallback. Error: {exc}"
            ),
            "available_metrics": available_metric_names,
        }

    return {
        "used": True,
        "available_metrics": available_metric_names,
        "scores": ragas_scores,
    }


def _evaluate_with_ragas_agent_metrics(
    sample: dict[str, Any],
    metric_objects: list[Any],
) -> dict[str, Any]:
    from datasets import Dataset
    from ragas import evaluate

    dataset = Dataset.from_list(
        [
            {
                "user_input": sample["user_input"],
                "response": sample["response"],
                "reference_tool_calls": sample["expected_tools"],
                "tool_calls": sample["actual_tools"],
                "expected_tools": sample["expected_tools"],
                "actual_tools": sample["actual_tools"],
            }
        ]
    )
    result = evaluate(dataset, metrics=metric_objects)
    if isinstance(result, dict):
        return dict(result)
    if hasattr(result, "to_pandas"):
        frame = result.to_pandas()
        if len(frame.index) == 0:
            return {}
        return {
            column: frame[column].iloc[0]
            for column in frame.columns
        }
    if hasattr(result, "scores") and result.scores:
        first_score = result.scores[0]
        if isinstance(first_score, dict):
            return dict(first_score)
    raise TypeError("RAGAS evaluate() returned an unsupported result shape")
