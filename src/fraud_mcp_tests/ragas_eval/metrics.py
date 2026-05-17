"""Metric loading helpers for optional RAGAS evaluations."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from fraud_mcp_tests.config import McpTestConfig


@dataclass(frozen=True)
class RagasMetricSpec:
    """A RAGAS metric object paired with local threshold metadata."""

    metric_name: str
    metric: Any
    threshold: float
    score_keys: tuple[str, ...]


def load_ragas_metrics(config: McpTestConfig) -> list[RagasMetricSpec]:
    """Load supported RAGAS metrics from the installed RAGAS version."""

    metrics_module = importlib.import_module("ragas.metrics")
    metric_specs: list[RagasMetricSpec] = []

    faithfulness = _first_available_metric(
        metrics_module,
        ("faithfulness", "Faithfulness"),
    )
    if faithfulness is not None:
        metric_specs.append(
            RagasMetricSpec(
                metric_name="faithfulness",
                metric=faithfulness,
                threshold=config.ragas_faithfulness_threshold,
                score_keys=("faithfulness",),
            )
        )

    response_relevancy = _first_available_metric(
        metrics_module,
        (
            "response_relevancy",
            "answer_relevancy",
            "ResponseRelevancy",
            "AnswerRelevancy",
        ),
    )
    if response_relevancy is not None:
        metric_specs.append(
            RagasMetricSpec(
                metric_name="response_relevancy",
                metric=response_relevancy,
                threshold=config.ragas_response_relevancy_threshold,
                score_keys=("response_relevancy", "answer_relevancy"),
            )
        )

    factual_correctness = _first_available_metric(
        metrics_module,
        (
            "factual_correctness",
            "FactualCorrectness",
        ),
    )
    if factual_correctness is not None:
        metric_specs.append(
            RagasMetricSpec(
                metric_name="factual_correctness",
                metric=factual_correctness,
                threshold=config.ragas_factual_correctness_threshold,
                score_keys=("factual_correctness",),
            )
        )

    return metric_specs


def _first_available_metric(
    metrics_module: ModuleType,
    candidate_names: tuple[str, ...],
) -> Any | None:
    for candidate_name in candidate_names:
        if not hasattr(metrics_module, candidate_name):
            continue

        metric = getattr(metrics_module, candidate_name)
        if isinstance(metric, type):
            try:
                return metric()
            except TypeError:
                continue
        return metric

    return None
