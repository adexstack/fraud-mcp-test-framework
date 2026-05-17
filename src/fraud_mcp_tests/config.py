"""Configuration loading for the Fraud MCP black-box test framework."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from dotenv import load_dotenv


DEFAULT_MCP_SERVER_URL = "https://fraud-mcp-platform.onrender.com/mcp"
DEFAULT_MCP_TRANSPORT = "streamable-http"
DEFAULT_RAGAS_MODEL = "gpt-4o-mini"
SUPPORTED_TRANSPORTS = {"http", "streamable-http"}
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class McpTestConfig:
    """Runtime configuration for connecting to the MCP server under test."""

    server_url: str | None
    transport: str = DEFAULT_MCP_TRANSPORT
    auth_token: str | None = None
    timeout_seconds: float = 30.0
    ragas_enabled: bool = False
    ragas_model: str = DEFAULT_RAGAS_MODEL
    ragas_faithfulness_threshold: float = 0.80
    ragas_response_relevancy_threshold: float = 0.75
    ragas_factual_correctness_threshold: float = 0.75
    agent_tool_call_f1_threshold: float = 0.90

    @property
    def is_configured(self) -> bool:
        return bool(self.server_url)

    @property
    def auth_headers(self) -> dict[str, str]:
        if not self.auth_token:
            return {}
        return {"Authorization": f"Bearer {self.auth_token}"}


def load_config(environ: Mapping[str, str] | None = None) -> McpTestConfig:
    """Load MCP test configuration from environment variables."""

    load_dotenv()
    env = environ if environ is not None else os.environ
    transport = env.get("MCP_TRANSPORT", DEFAULT_MCP_TRANSPORT).strip().lower()
    if transport not in SUPPORTED_TRANSPORTS:
        raise ValueError(
            "MCP_TRANSPORT must be one of "
            f"{sorted(SUPPORTED_TRANSPORTS)}, got {transport!r}"
        )

    timeout_raw = env.get("MCP_TIMEOUT_SECONDS", "30")
    timeout_seconds = _parse_float(timeout_raw, "MCP_TIMEOUT_SECONDS")

    if timeout_seconds <= 0:
        raise ValueError("MCP_TIMEOUT_SECONDS must be greater than zero")

    server_url = env.get("MCP_SERVER_URL", DEFAULT_MCP_SERVER_URL)
    auth_token = env.get("MCP_AUTH_TOKEN")
    ragas_model = env.get("RAGAS_MODEL", DEFAULT_RAGAS_MODEL)

    return McpTestConfig(
        server_url=server_url.strip() if server_url else None,
        transport=transport,
        auth_token=auth_token.strip() if auth_token else None,
        timeout_seconds=timeout_seconds,
        ragas_enabled=_parse_bool(env.get("RAGAS_ENABLED", "false"), "RAGAS_ENABLED"),
        ragas_model=ragas_model.strip() if ragas_model else DEFAULT_RAGAS_MODEL,
        ragas_faithfulness_threshold=_parse_threshold(
            env.get("RAGAS_FAITHFULNESS_THRESHOLD", "0.80"),
            "RAGAS_FAITHFULNESS_THRESHOLD",
        ),
        ragas_response_relevancy_threshold=_parse_threshold(
            env.get("RAGAS_RESPONSE_RELEVANCY_THRESHOLD", "0.75"),
            "RAGAS_RESPONSE_RELEVANCY_THRESHOLD",
        ),
        ragas_factual_correctness_threshold=_parse_threshold(
            env.get("RAGAS_FACTUAL_CORRECTNESS_THRESHOLD", "0.75"),
            "RAGAS_FACTUAL_CORRECTNESS_THRESHOLD",
        ),
        agent_tool_call_f1_threshold=_parse_threshold(
            env.get("AGENT_TOOL_CALL_F1_THRESHOLD", "0.90"),
            "AGENT_TOOL_CALL_F1_THRESHOLD",
        ),
    )


def _parse_bool(raw: str, name: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be one of true/false, yes/no, on/off, or 1/0")


def _parse_float(raw: str, name: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def _parse_threshold(raw: str, name: str) -> float:
    threshold = _parse_float(raw, name)
    if not 0 <= threshold <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return threshold
