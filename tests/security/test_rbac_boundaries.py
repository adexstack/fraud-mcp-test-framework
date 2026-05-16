from __future__ import annotations

import pytest

from fraud_mcp_tests.mcp_client import McpClient
from tests.security.helpers import (
    assert_auditable,
    assert_permission_failure,
    call_with_role,
    write_security_evidence,
)


pytestmark = pytest.mark.security


def test_rbac_matrix_contains_expected_roles_and_permissions(rbac_matrix) -> None:
    roles = rbac_matrix["roles"]

    assert set(roles) == {
        "analyst_l1",
        "analyst_l2",
        "analyst_l3",
        "investigator_manager",
        "auditor",
    }, "RBAC matrix must define all expected Fraud MCP roles."
    assert {"search_customer", "get_transaction", "score_transaction_risk"} <= set(
        roles["analyst_l1"]["allowed_tools"]
    ), "analyst_l1 must be limited to read/scoring tools."
    assert "create_fraud_case" in roles["analyst_l2"]["allowed_tools"], (
        "analyst_l2 must be able to create fraud cases."
    )
    assert "escalate_case" in roles["analyst_l3"]["allowed_tools"], (
        "analyst_l3 must be able to escalate fraud cases."
    )
    assert not roles["investigator_manager"]["denied_tools"], (
        "investigator_manager should have all operational actions."
    )
    assert {"create_fraud_case", "escalate_case"} <= set(
        roles["auditor"]["denied_tools"]
    ), "auditor must be read-only and unable to mutate case state."


@pytest.mark.parametrize("role", ["analyst_l1", "auditor"])
@pytest.mark.parametrize("tool_name", ["create_fraud_case", "escalate_case"])
@pytest.mark.live
def test_read_only_users_cannot_mutate_state(
    mcp_client: McpClient,
    rbac_matrix,
    role: str,
    tool_name: str,
    evidence_writer,
    trace_recorder,
) -> None:
    mcp_client.initialize()
    result = call_with_role(mcp_client, rbac_matrix, tool_name, role)

    assert_permission_failure(
        result,
        rbac_matrix,
        context=f"{role} calling {tool_name}",
    )
    assert_auditable(result, f"{role} calling {tool_name}")
    write_security_evidence(
        evidence_writer,
        f"rbac_{role}_{tool_name}",
        result,
        trace_recorder,
        {"role": role, "tool_name": tool_name},
    )


@pytest.mark.live
def test_l1_cannot_escalate_cases(
    mcp_client: McpClient,
    rbac_matrix,
    evidence_writer,
    trace_recorder,
) -> None:
    mcp_client.initialize()
    result = call_with_role(mcp_client, rbac_matrix, "escalate_case", "analyst_l1")

    assert_permission_failure(
        result,
        rbac_matrix,
        context="analyst_l1 escalating a case",
    )
    assert_auditable(result, "analyst_l1 escalating a case")
    write_security_evidence(
        evidence_writer,
        "rbac_l1_escalate_case",
        result,
        trace_recorder,
        {"role": "analyst_l1", "tool_name": "escalate_case"},
    )


@pytest.mark.parametrize("tool_name", ["create_fraud_case", "escalate_case"])
@pytest.mark.live
def test_auditor_cannot_create_or_escalate_cases(
    mcp_client: McpClient,
    rbac_matrix,
    tool_name: str,
    evidence_writer,
    trace_recorder,
) -> None:
    mcp_client.initialize()
    result = call_with_role(mcp_client, rbac_matrix, tool_name, "auditor")

    assert_permission_failure(
        result,
        rbac_matrix,
        context=f"auditor calling {tool_name}",
    )
    assert_auditable(result, f"auditor calling {tool_name}")
    write_security_evidence(
        evidence_writer,
        f"rbac_auditor_{tool_name}",
        result,
        trace_recorder,
        {"role": "auditor", "tool_name": tool_name},
    )
