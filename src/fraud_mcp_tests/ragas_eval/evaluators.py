"""Optional RAGAS evaluators for MCP-generated natural-language responses."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

import pytest

from fraud_mcp_tests.config import McpTestConfig, load_config
from fraud_mcp_tests.ragas_eval.metrics import RagasMetricSpec, load_ragas_metrics


class RagasEvaluationResult(TypedDict, total=False):
    metric_name: str
    score: float
    threshold: float
    passed: bool
    reason: str


def evaluate_investigation_summary(
    sample: Mapping[str, Any],
    config: McpTestConfig | None = None,
) -> list[RagasEvaluationResult]:
    """Evaluate an investigation summary sample with available RAGAS metrics."""

    resolved_config = _require_ragas_runtime(config)
    metric_specs = _load_supported_metrics(resolved_config)
    return _evaluate_sample_with_ragas(sample, metric_specs)


def evaluate_policy_grounding(
    sample: Mapping[str, Any],
    config: McpTestConfig | None = None,
) -> list[RagasEvaluationResult]:
    """Evaluate a policy-grounding sample with available RAGAS metrics."""

    resolved_config = _require_ragas_runtime(config)
    metric_specs = _load_supported_metrics(resolved_config)
    return _evaluate_sample_with_ragas(sample, metric_specs)


def write_ragas_report(
    results: Sequence[Mapping[str, Any]],
    output_path: str | Path,
) -> None:
    """Write RAGAS evaluation results to JSON."""

    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(list(results), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _require_ragas_runtime(config: McpTestConfig | None = None) -> McpTestConfig:
    resolved_config = config if config is not None else load_config()
    if not resolved_config.ragas_enabled:
        pytest.skip("RAGAS_ENABLED is not true")

    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is not configured")

    return resolved_config


def _load_supported_metrics(config: McpTestConfig) -> list[RagasMetricSpec]:
    try:
        metric_specs = load_ragas_metrics(config)
    except ImportError:
        pytest.skip("RAGAS is not installed")

    if not metric_specs:
        pytest.skip("Installed RAGAS version does not expose supported metrics")

    return metric_specs


def _evaluate_sample_with_ragas(
    sample: Mapping[str, Any],
    metric_specs: Sequence[RagasMetricSpec],
) -> list[RagasEvaluationResult]:
    try:
        scores = _run_ragas_evaluate(sample, metric_specs)
    except ImportError:
        pytest.skip("RAGAS evaluation dependencies are not installed")
    except (AttributeError, TypeError, ValueError) as exc:
        pytest.skip(f"Installed RAGAS version is not compatible: {exc}")

    return [_build_result(metric_spec, scores) for metric_spec in metric_specs]


def _run_ragas_evaluate(
    sample: Mapping[str, Any],
    metric_specs: Sequence[RagasMetricSpec],
) -> Mapping[str, Any]:
    from datasets import Dataset
    from ragas import evaluate

    dataset = Dataset.from_list([_to_ragas_row(sample)])
    result = evaluate(dataset, metrics=[metric_spec.metric for metric_spec in metric_specs])
    return _result_to_mapping(result)


def _to_ragas_row(sample: Mapping[str, Any]) -> dict[str, Any]:
    user_input = str(sample.get("user_input", ""))
    response = str(sample.get("response", ""))
    contexts = list(sample.get("retrieved_contexts", sample.get("contexts", [])))
    reference = sample.get("reference")

    row: dict[str, Any] = {
        "user_input": user_input,
        "response": response,
        "retrieved_contexts": contexts,
        "question": user_input,
        "answer": response,
        "contexts": contexts,
    }
    if reference is not None:
        row["reference"] = reference
        row["ground_truth"] = reference
    return row


def _result_to_mapping(result: Any) -> Mapping[str, Any]:
    if isinstance(result, Mapping):
        return result

    if hasattr(result, "to_pandas"):
        frame = result.to_pandas()
        if len(frame.index) == 0:
            return {}
        return {
            column: frame[column].iloc[0]
            for column in frame.columns
        }

    if hasattr(result, "scores"):
        scores = result.scores
        if isinstance(scores, Sequence) and scores:
            first_score = scores[0]
            if isinstance(first_score, Mapping):
                return first_score

    raise TypeError("RAGAS evaluate() returned an unsupported result shape")


def _build_result(
    metric_spec: RagasMetricSpec,
    scores: Mapping[str, Any],
) -> RagasEvaluationResult:
    score = _extract_score(metric_spec, scores)
    result: RagasEvaluationResult = {
        "metric_name": metric_spec.metric_name,
        "score": score,
        "threshold": metric_spec.threshold,
        "passed": score >= metric_spec.threshold,
    }

    reason = _extract_reason(metric_spec, scores)
    if reason:
        result["reason"] = reason

    return result


def _extract_score(metric_spec: RagasMetricSpec, scores: Mapping[str, Any]) -> float:
    for score_key in metric_spec.score_keys:
        if score_key in scores:
            return float(scores[score_key])

    raise ValueError(f"RAGAS result did not include {metric_spec.metric_name!r}")


def _extract_reason(
    metric_spec: RagasMetricSpec,
    scores: Mapping[str, Any],
) -> str | None:
    for score_key in metric_spec.score_keys:
        reason_key = f"{score_key}_reason"
        if reason_key in scores and scores[reason_key]:
            return str(scores[reason_key])
    return None
