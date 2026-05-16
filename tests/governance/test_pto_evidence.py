from __future__ import annotations

import json

import pytest

from fraud_mcp_tests.reporting import GOVERNANCE_SUMMARY_PATH, write_governance_summary


pytestmark = pytest.mark.governance

PTO_REQUIRED_SECTIONS = {
    "end_to_end_workflow_tests_passing",
    "auditability_evidence_generated",
    "latency_within_threshold",
    "regression_baseline_stable",
    "no_critical_safety_failures",
    "governance_metadata_available",
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
