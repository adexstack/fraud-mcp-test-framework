"""Trace capture for MCP JSON-RPC requests and responses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fraud_mcp_tests.evidence import sanitize_payload


@dataclass
class TraceRecord:
    test_name: str
    workflow_id: str
    trace_id: str | None
    tool_name: str
    input_arguments: dict[str, Any]
    response_summary: dict[str, Any]
    success: bool
    error: str | None
    latency_ms: float | None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    method: str | None = None
    status_code: int | None = None
    request: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return sanitize_payload(asdict(self))


class TraceRecorder:
    """In-memory trace recorder for a single pytest test."""

    def __init__(
        self,
        test_name: str = "unknown_test",
        workflow_id: str | None = None,
    ) -> None:
        self.test_name = test_name
        self.workflow_id = workflow_id or str(uuid4())
        self.entries: list[TraceRecord] = []

    def record_rpc(
        self,
        method: str,
        request: dict[str, Any],
        response: dict[str, Any],
        trace_id: str | None = None,
        latency_ms: float | None = None,
        status_code: int | None = None,
        error: str | None = None,
    ) -> None:
        tool_name = _tool_name(method, request)
        input_arguments = _input_arguments(method, request)
        success = error is None and not _is_error_response(response)
        self.entries.append(
            TraceRecord(
                test_name=self.test_name,
                workflow_id=self.workflow_id,
                trace_id=trace_id,
                tool_name=tool_name,
                input_arguments=sanitize_payload(input_arguments),
                response_summary=sanitize_payload(_response_summary(response)),
                success=success,
                error=error or _response_error(response),
                latency_ms=latency_ms,
                method=method,
                status_code=status_code,
                request=sanitize_payload(request),
                response=sanitize_payload(response),
            )
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "rpc": [entry.as_dict() for entry in self.entries],
        }


def _tool_name(method: str, request: dict[str, Any]) -> str:
    if method == "tools/call":
        params = request.get("params")
        if isinstance(params, dict) and isinstance(params.get("name"), str):
            return params["name"]
    return method


def _input_arguments(method: str, request: dict[str, Any]) -> dict[str, Any]:
    params = request.get("params")
    if not isinstance(params, dict):
        return {}
    if method == "tools/call":
        arguments = params.get("arguments")
        return dict(arguments) if isinstance(arguments, dict) else {}
    return dict(params)


def _response_summary(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result")
    if isinstance(result, dict):
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return _summarize_mapping(structured)
        return _summarize_mapping(result)
    if "error" in response:
        return {"error": response["error"]}
    return _summarize_mapping(response)


def _summarize_mapping(value: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in (
        "ok",
        "case_id",
        "transaction_id",
        "customer_id",
        "risk_level",
        "risk_score",
        "status",
        "error",
    ):
        if key in value:
            summary[key] = value[key]
    if not summary:
        summary["fields"] = sorted(value.keys())
    return summary


def _is_error_response(response: dict[str, Any]) -> bool:
    if "error" in response:
        return True
    result = response.get("result")
    if isinstance(result, dict):
        structured = result.get("structuredContent")
        return isinstance(structured, dict) and structured.get("ok") is False
    return False


def _response_error(response: dict[str, Any]) -> str | None:
    if "error" in response:
        return str(response["error"])
    result = response.get("result")
    if isinstance(result, dict):
        structured = result.get("structuredContent")
        if isinstance(structured, dict) and structured.get("ok") is False:
            return str(structured.get("error"))
    return None
