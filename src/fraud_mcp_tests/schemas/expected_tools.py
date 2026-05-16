"""Expected MCP tool inventory for the Fraud Detection MCP server."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpectedTool:
    name: str
    purpose: str
    required_arguments: tuple[str, ...]
    optional_arguments: tuple[str, ...]
    expected_response_fields: tuple[str, ...]
    risk_category: str
    owner: str
    governance_criticality: str


EXPECTED_TOOLS: tuple[ExpectedTool, ...] = (
    ExpectedTool(
        name="search_customer",
        purpose="Find a customer profile using known customer identifiers.",
        required_arguments=("customer_id",),
        optional_arguments=("role",),
        expected_response_fields=("customer_id", "matched_records", "match_confidence"),
        risk_category="customer_identification",
        owner="Fraud Operations",
        governance_criticality="medium",
    ),
    ExpectedTool(
        name="get_transaction",
        purpose="Retrieve transaction details needed for fraud investigation.",
        required_arguments=("transaction_id",),
        optional_arguments=("role",),
        expected_response_fields=(
            "transaction_id",
            "amount",
            "currency",
            "status",
            "customer_id",
        ),
        risk_category="transaction_lookup",
        owner="Fraud Operations",
        governance_criticality="medium",
    ),
    ExpectedTool(
        name="score_transaction_risk",
        purpose="Score a transaction for suspected fraud risk.",
        required_arguments=("transaction_id",),
        optional_arguments=("role",),
        expected_response_fields=(
            "transaction_id",
            "risk_score",
            "risk_level",
            "signals",
            "recommended_action",
        ),
        risk_category="fraud_risk_scoring",
        owner="Financial Crime Analytics",
        governance_criticality="high",
    ),
    ExpectedTool(
        name="create_fraud_case",
        purpose="Create a fraud investigation case from a suspicious transaction.",
        required_arguments=("transaction_id",),
        optional_arguments=("role",),
        expected_response_fields=(
            "case_id",
            "transaction_id",
            "customer_id",
            "status",
            "priority",
            "created_at",
        ),
        risk_category="case_management",
        owner="Fraud Case Management",
        governance_criticality="high",
    ),
    ExpectedTool(
        name="get_case_status",
        purpose="Retrieve the current status and assignment of a fraud case.",
        required_arguments=("case_id",),
        optional_arguments=("role",),
        expected_response_fields=("case_id", "status", "assigned_to", "updated_at"),
        risk_category="case_management",
        owner="Fraud Case Management",
        governance_criticality="medium",
    ),
    ExpectedTool(
        name="escalate_case",
        purpose="Escalate a fraud case for urgent review or specialist handling.",
        required_arguments=("case_id", "reason"),
        optional_arguments=("role",),
        expected_response_fields=(
            "case_id",
            "status",
            "escalation_reason",
            "updated_at",
        ),
        risk_category="case_escalation",
        owner="Fraud Operations",
        governance_criticality="high",
    ),
    ExpectedTool(
        name="generate_investigation_summary",
        purpose="Generate a concise investigation summary for audit and review.",
        required_arguments=("case_id",),
        optional_arguments=("role",),
        expected_response_fields=("case_id", "summary", "findings", "generated_at"),
        risk_category="investigation_reporting",
        owner="Fraud Governance",
        governance_criticality="high",
    ),
)

EXPECTED_TOOL_NAMES: list[str] = [tool.name for tool in EXPECTED_TOOLS]
