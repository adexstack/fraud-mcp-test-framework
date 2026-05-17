from __future__ import annotations

import json

import pytest

from fraud_mcp_tests import reporting
from fraud_mcp_tests.reporting import GOVERNANCE_SUMMARY_PATH, write_governance_summary


pytestmark = pytest.mark.governance

PTO_REQUIRED_SECTIONS = {
    "end_to_end_workflow_tests_passing",
    "auditability_evidence_generated",
    "latency_within_threshold",
    "regression_baseline_stable",
    "no_critical_safety_failures",
    "governance_metadata_available",
    "ragas_evaluation",
}


def test_pto_evidence_summary_file_contains_required_sections() -> None:
    path = write_governance_summary()

    assert path == GOVERNANCE_SUMMARY_PATH
    assert path.exists(), "PTO governance summary file must exist under reports/."

    summary = json.loads(path.read_text())
    assert "pto" in summary, "Governance summary must include a PTO section."
    missing = PTO_REQUIRED_SECTIONS - set(summary["pto"])
    assert not missing, f"PTO evidence summary is missing sections: {sorted(missing)}."


def test_pto_evidence_contains_required_operational_signals() -> None:
    path = write_governance_summary()
    pto = json.loads(path.read_text())["pto"]

    assert pto["auditability_evidence_generated"]["status"] in {"available", "missing"}
    assert pto["latency_within_threshold"]["threshold_ms"] is not None, (
        "PTO summary must include latency threshold evidence."
    )
    assert pto["regression_baseline_stable"]["status"] == "baselines_available", (
        "PTO summary must show regression baselines are available."
    )
    assert pto["no_critical_safety_failures"]["status"] == "safety_tests_present", (
        "PTO summary must show critical safety test coverage is present."
    )
    assert pto["governance_metadata_available"]["status"] == "available", (
        "PTO summary must include governance metadata readiness."
    )
    assert pto["ragas_evaluation"]["status"] in {
        "NOT_RUN",
        "PARTIAL",
        "PASS",
        "FAIL",
    }, "PTO summary must include optional RAGAS evaluation readiness."


def test_pto_ragas_evaluation_summarises_available_reports(
    tmp_path,
    monkeypatch,
) -> None:
    investigation_report = tmp_path / "investigation_summary_ragas.json"
    policy_report = tmp_path / "policy_grounding_ragas.json"
    agent_report = tmp_path / "agent_workflow_eval.json"

    investigation_report.write_text(
        json.dumps(
            [
                {
                    "metric_name": "faithfulness",
                    "score": 0.87,
                    "threshold": 0.80,
                    "passed": True,
                },
                {
                    "metric_name": "response_relevancy",
                    "score": 0.82,
                    "threshold": 0.75,
                    "passed": True,
                },
            ]
        ),
        encoding="utf-8",
    )
    policy_report.write_text(
        json.dumps(
            [
                {
                    "metric_name": "faithfulness",
                    "score": 0.91,
                    "threshold": 0.80,
                    "passed": True,
                }
            ]
        ),
        encoding="utf-8",
    )
    agent_report.write_text(
        json.dumps(
            {
                "deterministic_local_fallback": {
                    "tool_call_f1": 1.0,
                    "passed": True,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reporting,
        "RAGAS_INVESTIGATION_SUMMARY_REPORT",
        investigation_report,
    )
    monkeypatch.setattr(reporting, "RAGAS_POLICY_GROUNDING_REPORT", policy_report)
    monkeypatch.setattr(reporting, "RAGAS_AGENT_WORKFLOW_REPORT", agent_report)

    summary = reporting.build_governance_summary()

    expected_ragas_evaluation = {
        "enabled": True,
        "investigation_summary_faithfulness": 0.87,
        "response_relevancy": 0.82,
        "policy_grounding_passed": True,
        "agent_workflow_f1": 1.0,
        "status": "PASS",
    }
    assert summary["ragas_evaluation"] == expected_ragas_evaluation
    assert summary["pto"]["ragas_evaluation"] == expected_ragas_evaluation
