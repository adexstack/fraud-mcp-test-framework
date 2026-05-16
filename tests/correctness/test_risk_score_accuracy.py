from __future__ import annotations

from typing import Any

import pytest

from tests.correctness.conftest import risk_level, risk_score, transaction_by_id


pytestmark = [pytest.mark.correctness, pytest.mark.live]


def _scenario_cases(*scenario_names: str) -> list[dict[str, Any]]:
    from tests.correctness.conftest import _load_testdata

    transactions = _load_testdata("transactions.json")
    return [
        transaction
        for transaction in transactions
        if transaction["scenario"] in set(scenario_names)
    ]


@pytest.mark.parametrize(
    "transaction",
    _scenario_cases("low_risk"),
    ids=lambda transaction: transaction["scenario"],
)
def test_low_risk_transaction_returns_low_risk(transaction, score_transaction) -> None:
    response = score_transaction(transaction["transaction_id"])

    assert risk_level(response) == transaction["expected_risk_level"], (
        "Low-risk fixture transaction must be classified as LOW. "
        f"Transaction: {transaction['transaction_id']}. Response: {response}."
    )


@pytest.mark.parametrize(
    "transaction",
    _scenario_cases(
        "high_amount",
        "high_risk_destination_country",
        "pep_customer",
        "new_beneficiary",
        "unusual_transaction_hour",
    ),
    ids=lambda transaction: transaction["scenario"],
)
def test_single_risk_factor_increases_score(
    transaction,
    transaction_testdata,
    score_transaction,
) -> None:
    baseline = transaction_by_id(
        transaction_testdata,
        transaction["expected_score_greater_than"],
    )

    baseline_response = score_transaction(baseline["transaction_id"])
    scenario_response = score_transaction(transaction["transaction_id"])

    assert risk_score(scenario_response) > risk_score(baseline_response), (
        "Single-factor risk fixture must score higher than the low-risk baseline. "
        f"Scenario: {transaction['scenario']}. "
        f"Baseline response: {baseline_response}. Scenario response: {scenario_response}."
    )


@pytest.mark.parametrize(
    "transaction",
    _scenario_cases("multiple_risk_signals"),
    ids=lambda transaction: transaction["scenario"],
)
def test_multiple_risk_signals_produce_high_or_critical_risk(
    transaction,
    score_transaction,
) -> None:
    response = score_transaction(transaction["transaction_id"])

    assert risk_level(response) in set(transaction["expected_risk_levels"]), (
        "Multiple risk signals must produce HIGH or CRITICAL risk. "
        f"Transaction: {transaction['transaction_id']}. Response: {response}."
    )


@pytest.mark.parametrize(
    "transaction",
    _scenario_cases(
        "low_risk",
        "high_amount",
        "high_risk_destination_country",
        "pep_customer",
        "new_beneficiary",
        "unusual_transaction_hour",
        "multiple_risk_signals",
    ),
    ids=lambda transaction: transaction["scenario"],
)
def test_risk_score_is_within_zero_to_one_hundred(transaction, score_transaction) -> None:
    response = score_transaction(transaction["transaction_id"])
    bounds = transaction["risk_score_bounds"]
    score = risk_score(response)

    assert bounds["min"] <= score <= bounds["max"], (
        "Risk score must stay within the permitted 0-100 range. "
        f"Transaction: {transaction['transaction_id']}. Score: {score}. "
        f"Response: {response}."
    )
