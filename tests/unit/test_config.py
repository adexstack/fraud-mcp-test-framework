from __future__ import annotations

from fraud_mcp_tests.config import load_config


def test_ragas_threshold_defaults_are_realistic() -> None:
    config = load_config(
        {
            "MCP_SERVER_URL": "",
            "MCP_TRANSPORT": "streamable-http",
            "MCP_TIMEOUT_SECONDS": "30",
        }
    )

    assert config.ragas_faithfulness_threshold == 0.80
    assert config.ragas_response_relevancy_threshold == 0.75
    assert config.ragas_factual_correctness_threshold == 0.75
    assert config.agent_tool_call_f1_threshold == 0.90
    assert config.agent_goal_success_threshold == 0.85


def test_ragas_thresholds_can_be_overridden_from_environment() -> None:
    config = load_config(
        {
            "MCP_SERVER_URL": "",
            "MCP_TRANSPORT": "streamable-http",
            "MCP_TIMEOUT_SECONDS": "30",
            "RAGAS_FAITHFULNESS_THRESHOLD": "0.81",
            "RAGAS_RESPONSE_RELEVANCY_THRESHOLD": "0.76",
            "RAGAS_FACTUAL_CORRECTNESS_THRESHOLD": "0.77",
            "AGENT_TOOL_CALL_F1_THRESHOLD": "0.91",
            "AGENT_GOAL_SUCCESS_THRESHOLD": "0.86",
        }
    )

    assert config.ragas_faithfulness_threshold == 0.81
    assert config.ragas_response_relevancy_threshold == 0.76
    assert config.ragas_factual_correctness_threshold == 0.77
    assert config.agent_tool_call_f1_threshold == 0.91
    assert config.agent_goal_success_threshold == 0.86
