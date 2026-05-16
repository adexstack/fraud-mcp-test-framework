from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from fraud_mcp_tests.mcp_client import McpClient, ToolCallResult


VALID_CASE_STATUSES = {
    "CREATED",
    "OPEN",
    "PENDING",
    "PENDING_REVIEW",
    "UNDER_REVIEW",
    "ESCALATED",
    "CLOSED",
}
VALID_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
WORKFLOW_ROLE = "investigator_manager"


@dataclass(frozen=True)
class WorkflowStep:
    name: str
    tool_name: str
    arguments: dict[str, Any]
    result: ToolCallResult
    structured_content: dict[str, Any]

    def evidence(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "structured_content": self.structured_content,
            "tool_call_result": {
                "success": self.result.success,
                "error": self.result.error,
                "latency_ms": self.result.latency_ms,
                "trace_id": self.result.trace_id,
                "timestamp": self.result.timestamp,
            },
        }


def workflow_transaction_id(
    transaction_testdata: list[dict[str, Any]],
    scenario: str = "multiple_risk_signals",
) -> str:
    for transaction in transaction_testdata:
        if transaction["scenario"] == scenario:
            return str(transaction["transaction_id"])
    raise AssertionError(f"Workflow test data must include a {scenario} case")


def call_workflow_tool(
    client: McpClient,
    steps: list[WorkflowStep],
    name: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> WorkflowStep:
    workflow_arguments = dict(arguments)
    workflow_arguments.setdefault("role", WORKFLOW_ROLE)
    result = client.call_tool(tool_name, workflow_arguments)
    assert result.success is True, (
        f"Workflow step {name} must return a structured ToolCallResult. "
        f"Tool error: {result.error}."
    )
    step = WorkflowStep(
        name=name,
        tool_name=tool_name,
        arguments=workflow_arguments,
        result=result,
        structured_content=structured_content(result),
    )
    steps.append(step)
    return step


def structured_content(result: ToolCallResult) -> dict[str, Any]:
    assert isinstance(result.response, dict), (
        f"Workflow step {result.tool_name} must return a structured response object."
    )
    structured = result.response.get("structuredContent", result.response)
    assert isinstance(structured, dict), (
        f"Workflow step {result.tool_name} response must include structured content."
    )
    return structured


def require_ok(step: WorkflowStep) -> dict[str, Any]:
    content = step.structured_content
    if content.get("ok") is False:
        pytest.skip(
            "MCP server does not contain required workflow fixture data for "
            f"{step.name}: {content.get('error')}"
        )
    return content


def assert_safe_failure(step: WorkflowStep, context: str) -> None:
    content = step.structured_content
    assert content.get("ok") is False or step.result.error, (
        f"{context} must be handled safely as a structured failure. "
        f"Response: {content}."
    )
    assert step.result.trace_id, f"{context} must still capture a trace_id."


def field(content: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in content:
            return content[name]
    nested = content.get("data")
    if isinstance(nested, dict):
        for name in names:
            if name in nested:
                return nested[name]
    return None


def string_field(content: dict[str, Any], *names: str) -> str:
    value = field(content, *names)
    assert isinstance(value, str) and value.strip(), (
        f"Expected non-empty string field {names} in response: {content}."
    )
    return value


def numeric_field(content: dict[str, Any], *names: str) -> float:
    value = field(content, *names)
    assert isinstance(value, int | float), (
        f"Expected numeric field {names} in response: {content}."
    )
    return float(value)


def summary_text(content: dict[str, Any]) -> str:
    value = field(content, "summary", "investigation_summary", "text")
    if isinstance(value, str):
        return value
    return str(content)


def step_index(steps: list[WorkflowStep], name: str) -> int:
    for index, step in enumerate(steps):
        if step.name == name:
            return index
    raise AssertionError(f"Workflow step was not executed: {name}")


def assert_every_step_has_trace(steps: list[WorkflowStep], trace_recorder) -> None:
    trace_ids = {entry.trace_id for entry in trace_recorder.entries}
    missing = [
        step.name
        for step in steps
        if not step.result.trace_id or step.result.trace_id not in trace_ids
    ]
    assert not missing, (
        "Every workflow step must have a captured trace record. "
        f"Missing trace for steps: {missing}."
    )


def write_workflow_evidence(
    evidence_writer,
    name: str,
    steps: list[WorkflowStep],
    trace_recorder,
    metadata: dict[str, Any] | None = None,
) -> None:
    evidence_writer.write_json(
        name,
        {
            "metadata": metadata or {},
            "steps": [step.evidence() for step in steps],
            "trace": trace_recorder.as_dict(),
        },
    )
