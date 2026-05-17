from __future__ import annotations

import json
import sys
from types import ModuleType

import pytest

from fraud_mcp_tests.config import McpTestConfig
from fraud_mcp_tests.ragas_eval import evaluators
from fraud_mcp_tests.ragas_eval.evaluators import (
    evaluate_investigation_summary,
    evaluate_policy_grounding,
    write_ragas_report,
)
from fraud_mcp_tests.ragas_eval.metrics import RagasMetricSpec, load_ragas_metrics


pytestmark = [pytest.mark.ragas, pytest.mark.llm_eval]


def _enabled_config() -> McpTestConfig:
    return McpTestConfig(
        server_url="http://testserver/mcp",
        ragas_enabled=True,
        ragas_faithfulness_threshold=0.80,
        ragas_response_relevancy_threshold=0.75,
        ragas_factual_correctness_threshold=0.75,
    )


def test_evaluate_investigation_summary_skips_when_ragas_disabled() -> None:
    with pytest.raises(pytest.skip.Exception, match="RAGAS_ENABLED"):
        evaluate_investigation_summary(
            {"user_input": "Summarise", "response": "Summary", "contexts": []},
            config=McpTestConfig(server_url="http://testserver/mcp"),
        )


def test_evaluate_policy_grounding_skips_when_openai_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(pytest.skip.Exception, match="OPENAI_API_KEY"):
        evaluate_policy_grounding(
            {
                "user_input": "Summarise",
                "response": "Use cautious language.",
                "contexts": ["Policy requires cautious language."],
            },
            config=_enabled_config(),
        )


def test_evaluate_investigation_summary_returns_structured_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metric_specs = [
        RagasMetricSpec("faithfulness", object(), 0.80, ("faithfulness",)),
        RagasMetricSpec(
            "response_relevancy",
            object(),
            0.75,
            ("response_relevancy", "answer_relevancy"),
        ),
        RagasMetricSpec(
            "factual_correctness",
            object(),
            0.75,
            ("factual_correctness",),
        ),
    ]
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(evaluators, "load_ragas_metrics", lambda config: metric_specs)
    monkeypatch.setattr(
        evaluators,
        "_run_ragas_evaluate",
        lambda sample, specs: {
            "faithfulness": 0.91,
            "faithfulness_reason": "Grounded in transaction evidence.",
            "response_relevancy": 0.74,
            "factual_correctness": 0.88,
        },
    )

    results = evaluate_investigation_summary(
        {
            "user_input": "Summarise TXN-CRIT-001",
            "response": "TXN-CRIT-001 is high risk.",
            "contexts": ["TXN-CRIT-001 risk score is 92."],
            "reference": "Mention the high risk score.",
        },
        config=_enabled_config(),
    )

    assert results == [
        {
            "metric_name": "faithfulness",
            "score": 0.91,
            "threshold": 0.80,
            "passed": True,
            "reason": "Grounded in transaction evidence.",
        },
        {
            "metric_name": "response_relevancy",
            "score": 0.74,
            "threshold": 0.75,
            "passed": False,
        },
        {
            "metric_name": "factual_correctness",
            "score": 0.88,
            "threshold": 0.75,
            "passed": True,
        },
    ]


def test_evaluate_policy_grounding_uses_same_ragas_result_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metric_specs = [
        RagasMetricSpec("faithfulness", object(), 0.80, ("faithfulness",)),
    ]
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(evaluators, "load_ragas_metrics", lambda config: metric_specs)
    monkeypatch.setattr(
        evaluators,
        "_run_ragas_evaluate",
        lambda sample, specs: {"faithfulness": 0.83},
    )

    results = evaluate_policy_grounding(
        {
            "user_input": "Can we confirm fraud?",
            "response": "The evidence indicates elevated risk.",
            "contexts": ["Policy blocks final legal conclusions."],
        },
        config=_enabled_config(),
    )

    assert results == [
        {
            "metric_name": "faithfulness",
            "score": 0.83,
            "threshold": 0.80,
            "passed": True,
        }
    ]


def test_load_ragas_metrics_uses_available_metric_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FactualCorrectness:
        pass

    metrics_module = ModuleType("ragas.metrics")
    metrics_module.faithfulness = object()
    metrics_module.answer_relevancy = object()
    metrics_module.FactualCorrectness = FactualCorrectness
    monkeypatch.setitem(sys.modules, "ragas.metrics", metrics_module)

    metric_specs = load_ragas_metrics(_enabled_config())

    assert [metric_spec.metric_name for metric_spec in metric_specs] == [
        "faithfulness",
        "response_relevancy",
        "factual_correctness",
    ]
    assert [metric_spec.threshold for metric_spec in metric_specs] == [
        0.80,
        0.75,
        0.75,
    ]


def test_load_ragas_metrics_omits_unavailable_factual_correctness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics_module = ModuleType("ragas.metrics")
    metrics_module.faithfulness = object()
    metrics_module.response_relevancy = object()
    monkeypatch.setitem(sys.modules, "ragas.metrics", metrics_module)

    metric_specs = load_ragas_metrics(_enabled_config())

    assert [metric_spec.metric_name for metric_spec in metric_specs] == [
        "faithfulness",
        "response_relevancy",
    ]


def test_write_ragas_report(tmp_path) -> None:
    output_path = tmp_path / "ragas" / "summary.json"
    results = [
        {
            "metric_name": "faithfulness",
            "score": 0.84,
            "threshold": 0.80,
            "passed": True,
            "reason": "Grounded in evidence.",
        }
    ]

    write_ragas_report(results, output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == results


def test_ragas_row_uses_tool_evidence_as_retrieved_contexts() -> None:
    row = evaluators._to_ragas_row(
        {
            "user_input": (
                "Summarise the fraud investigation for transaction TXN-CRIT-001"
            ),
            "response": (
                "The transaction TXN-CRIT-001 was assessed as CRITICAL."
            ),
            "retrieved_contexts": [
                "Transaction TXN-CRIT-001 amount is 25000 GBP.",
                "Risk assessment score is 95 with signals: high amount, PEP.",
                "Case CASE-001 status is ESCALATED.",
            ],
            "reference": (
                "The summary should state the transaction risk level, case status, "
                "and escalation reason without claiming proven fraud."
            ),
        }
    )

    assert row["user_input"] == (
        "Summarise the fraud investigation for transaction TXN-CRIT-001"
    )
    assert row["response"] == (
        "The transaction TXN-CRIT-001 was assessed as CRITICAL."
    )
    assert row["retrieved_contexts"] == [
        "Transaction TXN-CRIT-001 amount is 25000 GBP.",
        "Risk assessment score is 95 with signals: high amount, PEP.",
        "Case CASE-001 status is ESCALATED.",
    ]
    assert row["reference"] == (
        "The summary should state the transaction risk level, case status, "
        "and escalation reason without claiming proven fraud."
    )
