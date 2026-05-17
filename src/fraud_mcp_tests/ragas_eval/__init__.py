"""Optional RAGAS evaluation helpers.

This package is intentionally dependency-free until RAGAS evaluations are
implemented and enabled by configuration.
"""

from fraud_mcp_tests.config import McpTestConfig


def is_enabled(config: McpTestConfig) -> bool:
    """Return whether optional RAGAS evaluations should run."""

    return config.ragas_enabled
