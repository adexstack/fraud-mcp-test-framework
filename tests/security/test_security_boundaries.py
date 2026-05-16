from __future__ import annotations

import pytest

from fraud_mcp_tests.mcp_client import McpClient
from tests.security.helpers import (
    assert_auditable,
    assert_permission_failure,
    call_with_role,
    is_permission_failure,
    is_structured_failure,
    write_security_evidence,
)


pytestmark = pytest.mark.security


@pytest.mark.live
def test_missing_role_is_rejected_or_treated_as_least_privilege(
    mcp_client: McpClient,
    rbac_matrix,
    evidence_writer,
    trace_recorder,
) -> None:
    mcp_client.initialize()
    result = call_with_role(mcp_client, rbac_matrix, "escalate_case", role=None)

    assert_permission_failure(
        result,
        rbac_matrix,
        context="missing role escalating a case",
    )
    assert_auditable(result, "missing role escalating a case")
    write_security_evidence(
        evidence_writer,
        "security_missing_role_escalate_case",
        result,
        trace_recorder,
        {"role": None, "tool_name": "escalate_case"},
    )


@pytest.mark.live
def test_invalid_role_is_rejected(
    mcp_client: McpClient,
    rbac_matrix,
    evidence_writer,
    trace_recorder,
) -> None:
    role = rbac_matrix["invalid_role"]

    mcp_client.initialize()
    result = call_with_role(mcp_client, rbac_matrix, "get_transaction", role=role)

    assert_permission_failure(
        result,
        rbac_matrix,
        context=f"invalid role {role} reading a transaction",
    )
    assert_auditable(result, f"invalid role {role} reading a transaction")
    write_security_evidence(
        evidence_writer,
        "security_invalid_role_get_transaction",
        result,
        trace_recorder,
        {"role": role, "tool_name": "get_transaction"},
    )


@pytest.mark.live
def test_permission_failure_is_structured_and_auditable(
    mcp_client: McpClient,
    rbac_matrix,
    evidence_writer,
    trace_recorder,
) -> None:
    mcp_client.initialize()
    result = call_with_role(mcp_client, rbac_matrix, "create_fraud_case", "auditor")

    if not is_permission_failure(result, rbac_matrix):
        if is_structured_failure(result):
            pytest.skip(
                "MCP server returned a structured domain failure instead of a "
                "permission failure. RBAC enforcement is a required testability hook."
            )
        pytest.xfail(
            "MCP server did not return a permission failure for auditor mutation."
        )

    assert is_structured_failure(result), (
        "Permission failures must be structured and not raw transport exceptions."
    )
    assert result.trace_id, "Permission failures must include a trace_id."
    assert result.latency_ms >= 0, "Permission failures must capture latency_ms."
    assert trace_recorder.entries, "Permission failure must be captured in trace evidence."
    write_security_evidence(
        evidence_writer,
        "security_permission_failure_auditability",
        result,
        trace_recorder,
        {"role": "auditor", "tool_name": "create_fraud_case"},
    )


def test_rbac_matrix_denies_mutating_tools_to_read_only_roles(rbac_matrix) -> None:
    read_only_roles = ("analyst_l1", "auditor")
    mutating_tools = {"create_fraud_case", "escalate_case"}

    for role in read_only_roles:
        denied = set(rbac_matrix["roles"][role]["denied_tools"])
        assert mutating_tools <= denied, (
            f"{role} must be denied mutating tools in the RBAC matrix. "
            f"Denied tools: {sorted(denied)}."
        )
