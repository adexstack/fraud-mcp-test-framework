from __future__ import annotations

from typing import Any

import pytest

from tests.correctness.conftest import recommended_action, signals


pytestmark = [pytest.mark.correctness, pytest.mark.live]


def _transactions_with_expected_signals() -> list[dict[str, Any]]:
    from tests.correctness.conftest import _load_testdata

    return [
        transaction
        for transaction in _load_testdata("transactions.json")
        if transaction.get("expected_signals")
    ]


def _transactions_with_expected_actions() -> list[dict[str, Any]]:
    from tests.correctness.conftest import _load_testdata

    return [
        transaction
        for transaction in _load_testdata("transactions.json")
        if transaction.get("expected_recommended_action")
        or transaction.get("expected_recommended_actions")
    ]


@pytest.mark.parametrize(
    "transaction",
    _transactions_with_expected_signals(),
    ids=lambda transaction: transaction["scenario"],
)
def test_expected_risk_signals_are_reported(transaction, score_transaction) -> None:
    response = score_transaction(transaction["transaction_id"])
    expected_signals = {signal.lower() for signal in transaction["expected_signals"]}

    assert expected_signals <= signals(response), (
        "Risk scoring response must include the expected business risk signals. "
        f"Transaction: {transaction['transaction_id']}. "
        f"Expected signals: {sorted(expected_signals)}. Response: {response}."
    )


@pytest.mark.parametrize(
    "transaction",
    _transactions_with_expected_actions(),
    ids=lambda transaction: transaction["scenario"],
)
def test_recommended_action_matches_risk_level_expectation(
    transaction,
    score_transaction,
) -> None:
    response = score_transaction(transaction["transaction_id"])
    actual_action = recommended_action(response)

    if "expected_recommended_actions" in transaction:
        expected_actions = set(transaction["expected_recommended_actions"])
        assert actual_action in expected_actions, (
            "Recommended action must match the expected action set for the "
            "fixture risk level. "
            f"Transaction: {transaction['transaction_id']}. "
            f"Expected one of: {sorted(expected_actions)}. Response: {response}."
        )
        return

    assert actual_action == transaction["expected_recommended_action"], (
        "Recommended action must match the expected action for the fixture risk level. "
        f"Transaction: {transaction['transaction_id']}. Response: {response}."
    )
