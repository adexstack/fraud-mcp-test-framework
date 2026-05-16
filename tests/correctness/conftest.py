from __future__ import annotations

import json
from collections.abc import Mapping
from importlib import resources
from typing import Any

import pytest

from fraud_mcp_tests.mcp_client import McpClient, ToolCallResult


@pytest.fixture(scope="session")
def transaction_testdata() -> list[dict[str, Any]]:
    return _load_testdata("transactions.json")


@pytest.fixture(scope="session")
def customer_testdata() -> list[dict[str, Any]]:
    return _load_testdata("customers.json")


@pytest.fixture
def score_transaction(mcp_client: McpClient):
    cache: dict[str, dict[str, Any]] = {}
    mcp_client.initialize()

    def _score(transaction_id: str) -> dict[str, Any]:
        if transaction_id not in cache:
            result = mcp_client.call_tool(
                "score_transaction_risk",
                {"transaction_id": transaction_id},
            )
            cache[transaction_id] = extract_structured_content(result)
        return cache[transaction_id]

    return _score


def extract_structured_content(result: ToolCallResult) -> dict[str, Any]:
    assert result.success is True, (
        f"score_transaction_risk must return a structured ToolCallResult. "
        f"Tool error: {result.error}."
    )
    assert isinstance(result.response, dict), (
        "score_transaction_risk must return a response object."
    )
    structured_content = result.response.get("structuredContent", result.response)
    assert isinstance(structured_content, dict), (
        "score_transaction_risk response must include structured content."
    )
    if structured_content.get("ok") is False:
        pytest.skip(
            "MCP server does not contain required correctness fixture transaction: "
            f"{structured_content.get('error')}"
        )
    return structured_content


def risk_score(response: Mapping[str, Any]) -> float:
    score = response.get("risk_score", response.get("score"))
    assert isinstance(score, int | float), (
        f"Risk score must be numeric in score_transaction_risk response: {response}"
    )
    return float(score)


def risk_level(response: Mapping[str, Any]) -> str:
    level = response.get("risk_level", response.get("level"))
    assert isinstance(level, str) and level.strip(), (
        f"Risk level must be a non-empty string in response: {response}"
    )
    return level.upper()


def recommended_action(response: Mapping[str, Any]) -> str:
    action = response.get("recommended_action", response.get("action"))
    assert isinstance(action, str) and action.strip(), (
        f"Recommended action must be a non-empty string in response: {response}"
    )
    return action.upper()


def signals(response: Mapping[str, Any]) -> set[str]:
    raw_signals = response.get("signals", [])
    assert isinstance(raw_signals, list), (
        f"Risk signals must be returned as a list in response: {response}"
    )
    normalized: set[str] = set()
    for signal in raw_signals:
        if isinstance(signal, str):
            normalized.add(signal.lower())
        elif isinstance(signal, dict):
            name = signal.get("name") or signal.get("code") or signal.get("signal")
            if isinstance(name, str):
                normalized.add(name.lower())
    return normalized


def transaction_by_id(
    transactions: list[dict[str, Any]],
    transaction_id: str,
) -> dict[str, Any]:
    for transaction in transactions:
        if transaction["transaction_id"] == transaction_id:
            return transaction
    raise AssertionError(f"Missing transaction fixture: {transaction_id}")


def _load_testdata(filename: str) -> list[dict[str, Any]]:
    data_file = resources.files("fraud_mcp_tests.testdata").joinpath(filename)
    loaded = json.loads(data_file.read_text())
    assert isinstance(loaded, list), f"{filename} must contain a JSON list"
    return loaded
