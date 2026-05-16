"""Configuration loading for the Fraud MCP black-box test framework."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from dotenv import load_dotenv


DEFAULT_MCP_SERVER_URL = "https://fraud-mcp-platform.onrender.com/mcp"
DEFAULT_MCP_TRANSPORT = "streamable-http"
SUPPORTED_TRANSPORTS = {"http", "streamable-http"}


@dataclass(frozen=True)
class McpTestConfig:
    """Runtime configuration for connecting to the MCP server under test."""

    server_url: str | None
    transport: str = DEFAULT_MCP_TRANSPORT
    auth_token: str | None = None
    timeout_seconds: float = 30.0

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
    try:
        timeout_seconds = float(timeout_raw)
    except ValueError as exc:
        raise ValueError("MCP_TIMEOUT_SECONDS must be a number") from exc

    if timeout_seconds <= 0:
        raise ValueError("MCP_TIMEOUT_SECONDS must be greater than zero")

    server_url = env.get("MCP_SERVER_URL", DEFAULT_MCP_SERVER_URL)
    auth_token = env.get("MCP_AUTH_TOKEN")

    return McpTestConfig(
        server_url=server_url.strip() if server_url else None,
        transport=transport,
        auth_token=auth_token.strip() if auth_token else None,
        timeout_seconds=timeout_seconds,
    )
