"""Readable input and output contracts for expected Fraud MCP tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


JsonSchema = dict[str, Any]


@dataclass(frozen=True)
class ToolContract:
    name: str
    input_schema: JsonSchema
    output_schema: JsonSchema
    error_schema: JsonSchema


ERROR_RESPONSE_SCHEMA: JsonSchema = {
    "type": "object",
    "additionalProperties": True,
    "required": ["error_code", "message", "trace_id", "retryable"],
    "properties": {
        "error_code": {"type": "string"},
        "message": {"type": "string"},
        "trace_id": {"type": "string"},
        "retryable": {"type": "boolean"},
        "details": {"type": "object"},
    },
}

ROLE_ARGUMENT_SCHEMA: JsonSchema = {"type": "string"}


def object_schema(
    properties: JsonSchema,
    required: tuple[str, ...],
    additional_properties: bool = False,
) -> JsonSchema:
    return {
        "type": "object",
        "additionalProperties": additional_properties,
        "required": list(required),
        "properties": properties,
    }


TOOL_CONTRACTS: dict[str, ToolContract] = {
    "search_customer": ToolContract(
        name="search_customer",
        input_schema=object_schema(
            {
                "customer_id": {"type": "string", "minLength": 1},
                "role": ROLE_ARGUMENT_SCHEMA,
            },
            required=("customer_id",),
        ),
        output_schema=object_schema(
            {
                "customer_id": {"type": "string"},
                "matched_records": {"type": "array"},
                "match_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            required=("customer_id", "matched_records", "match_confidence"),
            additional_properties=True,
        ),
        error_schema=ERROR_RESPONSE_SCHEMA,
    ),
    "get_transaction": ToolContract(
        name="get_transaction",
        input_schema=object_schema(
            {
                "transaction_id": {"type": "string", "minLength": 1},
                "role": ROLE_ARGUMENT_SCHEMA,
            },
            required=("transaction_id",),
        ),
        output_schema=object_schema(
            {
                "transaction_id": {"type": "string"},
                "amount": {"type": "number"},
                "currency": {"type": "string"},
                "status": {"type": "string"},
                "customer_id": {"type": "string"},
            },
            required=("transaction_id", "amount", "currency", "status", "customer_id"),
            additional_properties=True,
        ),
        error_schema=ERROR_RESPONSE_SCHEMA,
    ),
    "score_transaction_risk": ToolContract(
        name="score_transaction_risk",
        input_schema=object_schema(
            {
                "transaction_id": {"type": "string", "minLength": 1},
                "role": ROLE_ARGUMENT_SCHEMA,
            },
            required=("transaction_id",),
        ),
        output_schema=object_schema(
            {
                "transaction_id": {"type": "string"},
                "risk_score": {"type": "number", "minimum": 0, "maximum": 1},
                "risk_level": {"type": "string"},
                "signals": {"type": "array"},
                "recommended_action": {"type": "string"},
            },
            required=(
                "transaction_id",
                "risk_score",
                "risk_level",
                "signals",
                "recommended_action",
            ),
            additional_properties=True,
        ),
        error_schema=ERROR_RESPONSE_SCHEMA,
    ),
    "create_fraud_case": ToolContract(
        name="create_fraud_case",
        input_schema=object_schema(
            {
                "transaction_id": {"type": "string", "minLength": 1},
                "role": ROLE_ARGUMENT_SCHEMA,
            },
            required=("transaction_id",),
        ),
        output_schema=object_schema(
            {
                "case_id": {"type": "string"},
                "transaction_id": {"type": "string"},
                "customer_id": {"type": "string"},
                "status": {"type": "string"},
                "priority": {"type": "string"},
                "created_at": {"type": "string"},
            },
            required=(
                "case_id",
                "transaction_id",
                "customer_id",
                "status",
                "priority",
                "created_at",
            ),
            additional_properties=True,
        ),
        error_schema=ERROR_RESPONSE_SCHEMA,
    ),
    "get_case_status": ToolContract(
        name="get_case_status",
        input_schema=object_schema(
            {
                "case_id": {"type": "string", "minLength": 1},
                "role": ROLE_ARGUMENT_SCHEMA,
            },
            required=("case_id",),
        ),
        output_schema=object_schema(
            {
                "case_id": {"type": "string"},
                "status": {"type": "string"},
                "assigned_to": {"type": "string"},
                "updated_at": {"type": "string"},
            },
            required=("case_id", "status", "assigned_to", "updated_at"),
            additional_properties=True,
        ),
        error_schema=ERROR_RESPONSE_SCHEMA,
    ),
    "escalate_case": ToolContract(
        name="escalate_case",
        input_schema=object_schema(
            {
                "case_id": {"type": "string", "minLength": 1},
                "reason": {"type": "string", "minLength": 1},
                "role": ROLE_ARGUMENT_SCHEMA,
            },
            required=("case_id", "reason"),
        ),
        output_schema=object_schema(
            {
                "case_id": {"type": "string"},
                "status": {"type": "string"},
                "escalation_reason": {"type": "string"},
                "updated_at": {"type": "string"},
            },
            required=("case_id", "status", "escalation_reason", "updated_at"),
            additional_properties=True,
        ),
        error_schema=ERROR_RESPONSE_SCHEMA,
    ),
    "generate_investigation_summary": ToolContract(
        name="generate_investigation_summary",
        input_schema=object_schema(
            {
                "case_id": {"type": "string", "minLength": 1},
                "role": ROLE_ARGUMENT_SCHEMA,
            },
            required=("case_id",),
        ),
        output_schema=object_schema(
            {
                "case_id": {"type": "string"},
                "summary": {"type": "string"},
                "findings": {"type": "array"},
                "generated_at": {"type": "string"},
            },
            required=("case_id", "summary", "findings", "generated_at"),
            additional_properties=True,
        ),
        error_schema=ERROR_RESPONSE_SCHEMA,
    ),
}

TOOL_INPUT_SCHEMAS: dict[str, JsonSchema] = {
    name: contract.input_schema for name, contract in TOOL_CONTRACTS.items()
}

TOOL_RESPONSE_SCHEMAS: dict[str, JsonSchema] = {
    name: contract.output_schema for name, contract in TOOL_CONTRACTS.items()
}
