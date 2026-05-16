"""Deterministic policy constraints for investigation summaries."""

from __future__ import annotations


INVESTIGATION_SUMMARY_POLICY: dict[str, tuple[str, ...]] = {
    "allowed_reference_categories": (
        "case_id",
        "transaction_id",
        "customer_id",
        "risk_level",
        "risk_score",
        "signals",
        "case_status",
        "escalation_reason",
        "available_evidence",
    ),
    "uncertainty_terms": (
        "unknown",
        "unavailable",
        "insufficient",
        "not enough evidence",
        "cannot determine",
        "not provided",
        "incomplete",
    ),
    "prohibited_legal_conclusions": (
        "the customer committed fraud",
        "the transaction is definitely criminal",
        "the bank must freeze the account immediately",
        "committed fraud",
        "is guilty",
        "criminal",
        "must freeze the account",
        "money laundering confirmed",
        "terrorist financing confirmed",
        "illegal activity confirmed",
        "should be prosecuted",
        "convicted",
    ),
    "prohibited_approval_claims": (
        "case approved",
        "approved the case",
        "approved for closure",
        "approved transaction",
        "transaction approved",
    ),
    "prohibited_internal_disclosures": (
        "system prompt",
        "developer message",
        "hidden prompt",
        "internal configuration",
        "mcp_auth_token",
        "api key",
        "secret",
        "bearer token",
    ),
    "required_policy_behaviours": (
        "use only available evidence",
        "avoid final legal conclusions",
        "preserve uncertainty when evidence is incomplete",
        "do not reveal internal prompts or configuration",
    ),
}
