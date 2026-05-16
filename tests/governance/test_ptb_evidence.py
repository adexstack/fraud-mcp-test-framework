from __future__ import annotations

import json

import pytest

from fraud_mcp_tests.reporting import GOVERNANCE_SUMMARY_PATH, write_governance_summary


pytestmark = pytest.mark.governance

PTB_REQUIRED_SECTIONS = {
    "mcp_server_reachable",
    "expected_tools_discoverable",
    "schema_contracts_valid",
    "core_business_rules_passing",
    "negative_input_tests_passing",
    "rbac_security_tests_present",
    "trace_capture_enabled",
}


def test_ptb_evidence_summary_file_contains_required_sections() -> None:
    path = write_governance_summary()

    assert path == GOVERNANCE_SUMMARY_PATH
    assert path.exists(), "PTB/PTO governance summary file must exist under reports/."

    summary = json.loads(path.read_text())
    assert "ptb" in summary, "Governance summary must include a PTB section."
    missing = PTB_REQUIRED_SECTIONS - set(summary["ptb"])
    assert not missing, f"PTB evidence summary is missing sections: {sorted(missing)}."


def test_ptb_evidence_contains_required_readiness_signals() -> None:
    path = write_governance_summary()
    ptb = json.loads(path.read_text())["ptb"]

    assert ptb["mcp_server_reachable"]["status"] in {
        "evidence_available",
        "missing_or_not_yet_evidenced",
    }
    assert ptb["expected_tools_discoverable"]["expected_tools"], (
        "PTB summary must list expected MCP tools."
    )
    assert ptb["schema_contracts_valid"]["contract_count"] > 0, (
        "PTB summary must include schema contract coverage."
    )
    assert ptb["rbac_security_tests_present"]["status"] == "present", (
        "PTB summary must show RBAC/security test coverage is present."
    )
    assert ptb["trace_capture_enabled"]["status"] == "enabled", (
        "PTB summary must show trace capture is enabled."
    )
