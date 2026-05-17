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


def load_investigation_summary_metrics(config: McpTestConfig) -> list[RagasMetricSpec]:
    """Faithfulness only: checks the summary is grounded in evidence contexts."""
    return _load_faithfulness_metric(config)


def load_policy_grounding_metrics(config: McpTestConfig) -> list[RagasMetricSpec]:
    """Faithfulness only: checks the summary is grounded in policy + data contexts."""
    return _load_faithfulness_metric(config)


def _load_faithfulness_metric(config: McpTestConfig) -> list[RagasMetricSpec]:
    metrics_module = importlib.import_module("ragas.metrics")
    faithfulness = _first_available_metric(
        metrics_module,
        ("faithfulness", "Faithfulness"),
    )
    if faithfulness is None:
        return []
    return [
        RagasMetricSpec(
            metric_name="faithfulness",
            metric=faithfulness,
            threshold=config.ragas_faithfulness_threshold,
            score_keys=("faithfulness",),
        )
    ]


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
