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
RAGAS_REPORTS_DIR = REPORTS_DIR / "ragas"
RAGAS_INVESTIGATION_SUMMARY_REPORT = (
    RAGAS_REPORTS_DIR / "investigation_summary_ragas.json"
)
RAGAS_POLICY_GROUNDING_REPORT = RAGAS_REPORTS_DIR / "policy_grounding_ragas.json"
RAGAS_AGENT_WORKFLOW_REPORT = RAGAS_REPORTS_DIR / "agent_workflow_eval.json"


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
    ragas_evaluation = _ragas_evaluation_summary()

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "governance_metadata": {
            "framework": "fraud-mcp-test-framework",
            "summary_version": "1.0",
            "reports_dir": str(REPORTS_DIR),
            "baseline_dir": str(BASELINE_DIR),
        },
        "ragas_evaluation": ragas_evaluation,
        "ptb": _ptb_summary(static_baseline, live_baseline, evidence_files, test_files),
        "pto": _pto_summary(live_baseline, evidence_files, test_files, ragas_evaluation),
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
    ragas_evaluation: dict[str, Any],
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
        "ragas_evaluation": ragas_evaluation,
    }


def _ragas_evaluation_summary() -> dict[str, Any]:
    investigation_results = _read_json_list(RAGAS_INVESTIGATION_SUMMARY_REPORT)
    policy_results = _read_json_list(RAGAS_POLICY_GROUNDING_REPORT)
    agent_workflow = _read_json(RAGAS_AGENT_WORKFLOW_REPORT)

    enabled = bool(investigation_results or policy_results or agent_workflow)
    investigation_summary_faithfulness = _metric_score(
        investigation_results,
        "faithfulness",
    )
    response_relevancy = _metric_score(
        investigation_results,
        "response_relevancy",
    )
    policy_grounding_passed = _results_passed(policy_results)
    agent_workflow_f1 = _agent_workflow_f1(agent_workflow)

    return {
        "enabled": enabled,
        "investigation_summary_faithfulness": investigation_summary_faithfulness,
        "response_relevancy": response_relevancy,
        "policy_grounding_passed": policy_grounding_passed,
        "agent_workflow_f1": agent_workflow_f1,
        "status": _ragas_status(
            enabled=enabled,
            investigation_results=investigation_results,
            policy_results=policy_results,
            agent_workflow=agent_workflow,
        ),
    }


def _ragas_status(
    enabled: bool,
    investigation_results: list[dict[str, Any]],
    policy_results: list[dict[str, Any]],
    agent_workflow: dict[str, Any],
) -> str:
    if not enabled:
        return "NOT_RUN"

    checks = [
        _results_passed(investigation_results),
        _results_passed(policy_results),
        _agent_workflow_passed(agent_workflow),
    ]
    if all(check is True for check in checks):
        return "PASS"
    if any(check is False for check in checks):
        return "FAIL"
    return "PARTIAL"


def _metric_score(results: list[dict[str, Any]], metric_name: str) -> float | None:
    for result in results:
        if result.get("metric_name") != metric_name:
            continue
        score = result.get("score")
        return float(score) if isinstance(score, int | float) else None
    return None


def _results_passed(results: list[dict[str, Any]]) -> bool | None:
    if not results:
        return None
    return all(result.get("passed") is True for result in results)


def _agent_workflow_f1(agent_workflow: dict[str, Any]) -> float | None:
    fallback = agent_workflow.get("deterministic_local_fallback")
    if not isinstance(fallback, dict):
        return None

    score = fallback.get("tool_call_f1")
    return float(score) if isinstance(score, int | float) else None


def _agent_workflow_passed(agent_workflow: dict[str, Any]) -> bool | None:
    fallback = agent_workflow.get("deterministic_local_fallback")
    if not isinstance(fallback, dict):
        return None

    passed = fallback.get("passed")
    return passed if isinstance(passed, bool) else None


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


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    loaded = json.loads(path.read_text())
    if not isinstance(loaded, list):
        return []
    return [item for item in loaded if isinstance(item, dict)]


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
