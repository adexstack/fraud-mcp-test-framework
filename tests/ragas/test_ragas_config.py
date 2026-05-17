from __future__ import annotations

import pytest

from fraud_mcp_tests.config import McpTestConfig
from fraud_mcp_tests.ragas_eval import is_enabled


pytestmark = [pytest.mark.ragas, pytest.mark.llm_eval]


def test_ragas_layer_uses_enabled_config(ragas_config: McpTestConfig) -> None:
    assert is_enabled(ragas_config)
