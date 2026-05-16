"""Black-box MCP client abstraction used by pytest tests."""

from __future__ import annotations

import itertools
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx

from fraud_mcp_tests.config import McpTestConfig
from fraud_mcp_tests.trace import TraceRecorder


JsonObject = dict[str, Any]


class McpClientError(RuntimeError):
    """Raised when the external MCP server returns an invalid response."""


@dataclass(frozen=True)
class RequestResponseMetadata:
    """Metadata captured for a single black-box interaction with the server."""

    trace_id: str
    method: str
    url: str
    request: JsonObject
    response: JsonObject | None
    status_code: int | None
    latency_ms: float
    timestamp: str
    error: str | None = None


@dataclass(frozen=True)
class ToolCallResult:
    """Structured result returned from an MCP tool invocation."""

    tool_name: str
    arguments: dict[str, Any]
    success: bool
    response: JsonObject | None
    error: str | None
    latency_ms: float
    trace_id: str
    timestamp: str
    metadata: RequestResponseMetadata | None = field(default=None, repr=False)


class McpClient:
    """Minimal JSON-RPC client for HTTP-based MCP servers."""

    def __init__(
        self,
        config: McpTestConfig,
        trace_recorder: TraceRecorder | None = None,
        http_client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not config.server_url:
            raise ValueError("MCP_SERVER_URL is required to create an MCP client")
        self._config = config
        self._trace_recorder = trace_recorder
        self._ids = itertools.count(1)
        self._session_id: str | None = None
        self.metadata: list[RequestResponseMetadata] = []
        self._client = http_client or httpx.Client(
            base_url=config.server_url,
            timeout=config.timeout_seconds,
            headers=self._headers(),
            transport=transport,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def health_check(self) -> bool:
        """Return whether the configured MCP endpoint is reachable."""

        trace_id = self._new_trace_id()
        timestamp = self._timestamp()
        started = perf_counter()
        request: JsonObject = {"method": "GET", "url": str(self._client.base_url)}
        response_body: JsonObject | None = None
        status_code: int | None = None
        error: str | None = None

        try:
            response = self._client.get("")
            status_code = response.status_code
            response_body = {"text": response.text[:500]}
            return response.status_code < 500
        except httpx.RequestError as exc:
            error = str(exc)
            return False
        finally:
            latency_ms = self._elapsed_ms(started)
            metadata = self._capture_metadata(
                trace_id=trace_id,
                method="health_check",
                request=request,
                response=response_body,
                status_code=status_code,
                latency_ms=latency_ms,
                timestamp=timestamp,
                error=error,
            )
            if self._trace_recorder:
                self._trace_recorder.record_rpc(
                    "health_check",
                    request,
                    response_body or {},
                    trace_id=metadata.trace_id,
                    latency_ms=metadata.latency_ms,
                    status_code=metadata.status_code,
                    error=metadata.error,
                )

    def initialize(self) -> JsonObject:
        """Initialize an MCP session and return the server result payload."""

        return self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "fraud-mcp-test-framework",
                    "version": "0.1.0",
                },
            },
        )

    def list_tools(self) -> list[JsonObject]:
        """Return tools advertised by the MCP server."""

        result = self.request("tools/list")
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise McpClientError("tools/list response must include a tools list")
        return tools

    def call_tool(
        self,
        tool_name: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> ToolCallResult:
        """Invoke a named MCP tool and return a structured black-box result."""

        tool_arguments = dict(arguments or {})
        trace_id = self._new_trace_id()
        timestamp = self._timestamp()
        started = perf_counter()
        response: JsonObject | None = None
        error: str | None = None

        try:
            response = self.request(
                "tools/call",
                {"name": tool_name, "arguments": tool_arguments},
                trace_id=trace_id,
                timestamp=timestamp,
            )
            success = True
        except Exception as exc:  # The result object is the test boundary.
            success = False
            error = str(exc)

        latency_ms = self._elapsed_ms(started)
        metadata = self._find_metadata(trace_id)
        result_trace_id = self._extract_trace_id(response, metadata) or trace_id
        return ToolCallResult(
            tool_name=tool_name,
            arguments=tool_arguments,
            success=success,
            response=response,
            error=error,
            latency_ms=latency_ms,
            trace_id=result_trace_id,
            timestamp=timestamp,
            metadata=metadata,
        )

    def request(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        trace_id: str | None = None,
        timestamp: str | None = None,
    ) -> JsonObject:
        """Send a JSON-RPC request and return the MCP result object."""

        request_id = next(self._ids)
        trace_id = trace_id or self._new_trace_id()
        timestamp = timestamp or self._timestamp()
        payload: JsonObject = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = dict(params)

        started = perf_counter()
        response_body: JsonObject | None = None
        status_code: int | None = None
        error: str | None = None

        try:
            response = self._client.post(
                "",
                json=payload,
                headers=self._request_headers(trace_id),
            )
            status_code = response.status_code
            response.raise_for_status()
            self._capture_session_id(response)
            body = self._parse_response_body(response)
            response_body = body if isinstance(body, dict) else {"raw": body}

            if not isinstance(body, dict):
                raise McpClientError(f"{method} response must be a JSON object")
            if body.get("id") != request_id:
                raise McpClientError(
                    f"{method} response id mismatch: expected {request_id}, "
                    f"got {body.get('id')}"
                )
            if "error" in body:
                raise McpClientError(f"{method} failed: {body['error']}")
            result = body.get("result")
            if not isinstance(result, dict):
                raise McpClientError(f"{method} response must include a result object")
            return result
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            latency_ms = self._elapsed_ms(started)
            metadata = self._capture_metadata(
                trace_id=trace_id,
                method=method,
                request=payload,
                response=response_body,
                status_code=status_code,
                latency_ms=latency_ms,
                timestamp=timestamp,
                error=error,
            )
            if self._trace_recorder:
                self._trace_recorder.record_rpc(
                    method,
                    payload,
                    response_body or {},
                    trace_id=metadata.trace_id,
                    latency_ms=metadata.latency_ms,
                    status_code=metadata.status_code,
                    error=metadata.error,
                )

    def __enter__(self) -> McpClient:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **self._config.auth_headers,
        }

    def _request_headers(self, trace_id: str) -> dict[str, str]:
        headers = {"X-Trace-Id": trace_id}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _capture_session_id(self, response: httpx.Response) -> None:
        session_id = response.headers.get("mcp-session-id")
        if session_id:
            self._session_id = session_id

    def _parse_response_body(self, response: httpx.Response) -> JsonObject:
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            body = response.json()
            if not isinstance(body, dict):
                raise McpClientError("MCP response must be a JSON object")
            return body

        for line in response.text.splitlines():
            if not line.startswith("data:"):
                continue
            body = json.loads(line.removeprefix("data:").strip())
            if not isinstance(body, dict):
                raise McpClientError("MCP SSE data payload must be a JSON object")
            return body

        raise McpClientError("MCP SSE response did not contain a data payload")

    def _capture_metadata(
        self,
        trace_id: str,
        method: str,
        request: JsonObject,
        response: JsonObject | None,
        status_code: int | None,
        latency_ms: float,
        timestamp: str,
        error: str | None = None,
    ) -> RequestResponseMetadata:
        metadata = RequestResponseMetadata(
            trace_id=trace_id,
            method=method,
            url=str(self._client.base_url),
            request=request,
            response=response,
            status_code=status_code,
            latency_ms=latency_ms,
            timestamp=timestamp,
            error=error,
        )
        self.metadata.append(metadata)
        return metadata

    def _find_metadata(self, trace_id: str) -> RequestResponseMetadata | None:
        for metadata in reversed(self.metadata):
            if metadata.trace_id == trace_id:
                return metadata
        return None

    @staticmethod
    def _extract_trace_id(
        response: JsonObject | None,
        metadata: RequestResponseMetadata | None,
    ) -> str | None:
        if response and isinstance(response.get("trace_id"), str):
            return response["trace_id"]
        if not metadata or not metadata.response:
            return None
        if isinstance(metadata.response.get("trace_id"), str):
            return metadata.response["trace_id"]
        result = metadata.response.get("result")
        if isinstance(result, dict) and isinstance(result.get("trace_id"), str):
            return result["trace_id"]
        return None

    @staticmethod
    def _new_trace_id() -> str:
        return str(uuid4())

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((perf_counter() - started) * 1000, 3)
