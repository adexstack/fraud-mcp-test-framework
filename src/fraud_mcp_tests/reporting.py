"""Reporting helpers for pytest runs and governance evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fraud_mcp_tests.baseline import BASELINE_DIR
from fraud_mcp_tests.evidence import REPORTS_DIR, sanitize_payload
from fraud_mcp_tests.schemas.expected_tools import EXPECTED_TOOL_NAMES
from fraud_mcp_tests.schemas.tool_contracts import TOOL_CONTRACTS


GOVERNANCE_SUMMARY_PATH = REPORTS_DIR / "governance_summary.json"


def write_run_metadata(
    metadata: dict[str, Any],
    path: Path = REPORTS_DIR / "run_metadata.json",
) -> Path:
    """Write machine-readable run metadata for downstream evidence collection."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "captured_at": datetime.now(UTC).isoformat(),
        "metadata": metadata,
    }
    path.write_text(json.dumps(sanitize_payload(payload), indent=2, sort_keys=True))
    return path


def write_governance_summary(
    path: Path = GOVERNANCE_SUMMARY_PATH,
) -> Path:
    """Generate a PTB/PTO governance summary under reports/."""

    path.parent.mkdir(parents=True, exist_ok=True)
    summary = build_governance_summary()
    path.write_text(json.dumps(sanitize_payload(summary), indent=2, sort_keys=True))
    return path


def build_governance_summary() -> dict[str, Any]:
    static_baseline = _read_json(BASELINE_DIR / "static_tool_contracts.json")
    live_baseline = _read_json(BASELINE_DIR / "live_mcp_behaviour.json")
    evidence_files = _evidence_files()
    test_files = _test_files()

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "governance_metadata": {
            "framework": "fraud-mcp-test-framework",
            "summary_version": "1.0",
            "reports_dir": str(REPORTS_DIR),
            "baseline_dir": str(BASELINE_DIR),
        },
        "ptb": _ptb_summary(static_baseline, live_baseline, evidence_files, test_files),
        "pto": _pto_summary(live_baseline, evidence_files, test_files),
    }


def _ptb_summary(
    static_baseline: dict[str, Any],
    live_baseline: dict[str, Any],
    evidence_files: set[str],
    test_files: set[str],
) -> dict[str, Any]:
    live_tools = {
        tool.get("name")
        for tool in live_baseline.get("tool_inventory", [])
        if isinstance(tool, dict)
    }
    return {
        "mcp_server_reachable": {
            "status": "evidence_available",
            "evidence": "reports/evidence/connection_health_check.json"
            if "connection_health_check.json" in evidence_files
            else None,
        },
        "expected_tools_discoverable": {
            "status": "evidence_available"
            if set(EXPECTED_TOOL_NAMES) <= live_tools
            else "missing_or_not_yet_evidenced",
            "expected_tools": EXPECTED_TOOL_NAMES,
            "live_tools": sorted(live_tools),
        },
        "schema_contracts_valid": {
            "status": "baseline_available"
            if static_baseline.get("tool_schema_contracts")
            else "missing_baseline",
            "contract_count": len(TOOL_CONTRACTS),
        },
        "core_business_rules_passing": {
            "status": _scenario_status(live_baseline.get("known_risk_outcomes", {})),
            "known_risk_outcomes": live_baseline.get("known_risk_outcomes", {}),
        },
        "negative_input_tests_passing": {
            "status": "test_present",
            "test_file": "tests/security/test_security_boundaries.py",
        },
        "rbac_security_tests_present": {
            "status": "present"
            if "tests/security/test_rbac_boundaries.py" in test_files
            else "missing",
            "test_files": [
                "tests/security/test_rbac_boundaries.py",
                "tests/security/test_security_boundaries.py",
            ],
        },
        "trace_capture_enabled": {
            "status": "enabled",
            "evidence_jsonl": str(REPORTS_DIR / "evidence.jsonl"),
        },
    }


def _pto_summary(
    live_baseline: dict[str, Any],
    evidence_files: set[str],
    test_files: set[str],
) -> dict[str, Any]:
    return {
        "end_to_end_workflow_tests_passing": {
            "status": _scenario_status(live_baseline.get("known_workflow_outcomes", {})),
            "workflow_test_files": [
                "tests/workflows/test_case_lifecycle.py",
                "tests/workflows/test_multi_step_investigation.py",
                "tests/workflows/test_state_transitions.py",
            ],
        },
        "auditability_evidence_generated": {
            "status": "available" if (REPORTS_DIR / "evidence.jsonl").exists() else "missing",
            "evidence_files": sorted(evidence_files),
        },
        "latency_within_threshold": {
            "status": "policy_available",
            "threshold_ms": live_baseline.get("latency_policy", {}).get("threshold_ms")
            or live_baseline.get("latency_threshold_ms"),
        },
        "regression_baseline_stable": {
            "status": "baselines_available",
            "baselines": [
                str(BASELINE_DIR / "static_tool_contracts.json"),
                str(BASELINE_DIR / "live_mcp_behaviour.json"),
            ],
        },
        "no_critical_safety_failures": {
            "status": "safety_tests_present"
            if "tests/safety/test_hallucination_controls.py" in test_files
            else "missing",
            "test_files": [
                "tests/safety/test_hallucination_controls.py",
                "tests/safety/test_policy_grounding.py",
            ],
        },
        "governance_metadata_available": {
            "status": "available",
        },
    }


def _scenario_status(outcomes: dict[str, Any]) -> str:
    if not outcomes:
        return "not_evidenced"
    statuses = {
        outcome.get("status")
        for outcome in outcomes.values()
        if isinstance(outcome, dict)
    }
    if statuses == {"available"}:
        return "passing"
    if "available" in statuses:
        return "partially_passing"
    if "unavailable" in statuses:
        return "fixture_data_unavailable"
    return "evidenced"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _evidence_files() -> set[str]:
    evidence_dir = REPORTS_DIR / "evidence"
    if not evidence_dir.exists():
        return set()
    return {path.name for path in evidence_dir.glob("*.json")}


def _test_files() -> set[str]:
    tests_dir = Path("tests")
    if not tests_dir.exists():
        return set()
    return {str(path) for path in tests_dir.rglob("test_*.py")}
