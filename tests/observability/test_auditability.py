from __future__ import annotations

import json

import pytest

from fraud_mcp_tests.evidence import EvidenceWriter, REDACTED, sanitize_payload


pytestmark = pytest.mark.observability


def test_audit_evidence_is_written_as_jsonl_under_reports(tmp_path) -> None:
    writer = EvidenceWriter(reports_dir=tmp_path / "reports")

    path = writer.write_jsonl(
        "ptb_trace_review",
        {
            "trace": {
                "test_name": "test_case",
                "workflow_id": "workflow-001",
                "trace_id": "trace-001",
                "tool_name": "score_transaction_risk",
                "success": True,
            }
        },
    )

    assert path.name == "evidence.jsonl"
    assert path.parent.name == "reports"
    lines = path.read_text().splitlines()
    assert len(lines) == 1, "Evidence JSONL must contain one JSON object per line."
    record = json.loads(lines[0])
    assert record["name"] == "ptb_trace_review"
    assert record["payload"]["trace"]["workflow_id"] == "workflow-001"
    assert record["captured_at"], "Evidence record must include captured_at."


def test_audit_evidence_does_not_expose_secrets(tmp_path) -> None:
    writer = EvidenceWriter(reports_dir=tmp_path / "reports")
    secret = "super-secret-token"

    path = writer.write_jsonl(
        "secret_sanitisation",
        {
            "headers": {"Authorization": f"Bearer {secret}"},
            "config": {"MCP_AUTH_TOKEN": secret},
            "nested": {"api_key": "abc123"},
        },
    )

    content = path.read_text()
    assert secret not in content
    assert "abc123" not in content
    assert REDACTED in content


def test_sanitised_trace_evidence_can_be_used_for_ptb_pto_review(
    observed_mcp_client,
    observed_trace_recorder,
    tmp_path,
) -> None:
    writer = EvidenceWriter(reports_dir=tmp_path / "reports")
    observed_mcp_client.call_tool(
        "score_transaction_risk",
        {
            "transaction_id": "txn_observed_001",
            "auth_token": "do-not-write-me",
        },
    )

    path = writer.write_jsonl(
        "ptb_pto_trace_record",
        {"trace": observed_trace_recorder.as_dict()},
    )
    record = json.loads(path.read_text().splitlines()[0])
    trace = record["payload"]["trace"]["rpc"][0]

    for field in (
        "test_name",
        "workflow_id",
        "trace_id",
        "tool_name",
        "input_arguments",
        "response_summary",
        "success",
        "latency_ms",
        "timestamp",
    ):
        assert field in trace, f"PTB/PTO trace evidence must include {field}."
    assert "do-not-write-me" not in path.read_text()


def test_sanitize_payload_redacts_sensitive_fields() -> None:
    payload = {
        "token": "secret",
        "safe": "visible",
        "nested": {"password": "hidden", "value": 1},
    }

    assert sanitize_payload(payload) == {
        "token": REDACTED,
        "safe": "visible",
        "nested": {"password": REDACTED, "value": 1},
    }
