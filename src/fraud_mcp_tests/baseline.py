"""Baseline snapshot utilities for regression impact testing."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASELINE_DIR = Path("reports") / "baselines"
UPDATE_BASELINE_ENV = "UPDATE_BASELINE"


@dataclass(frozen=True)
class BaselineComparison:
    baseline_path: Path
    current: dict[str, Any]
    expected: dict[str, Any]
    differences: list[str]
    updated: bool = False


def update_baseline_enabled() -> bool:
    return os.getenv(UPDATE_BASELINE_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }


def compare_or_update_baseline(
    name: str,
    current: dict[str, Any],
    baseline_dir: Path = BASELINE_DIR,
) -> BaselineComparison:
    baseline_dir.mkdir(parents=True, exist_ok=True)
    path = baseline_dir / f"{name}.json"
    current = _json_normalize(current)

    if update_baseline_enabled() or not path.exists():
        if not update_baseline_enabled() and not path.exists():
            raise AssertionError(
                f"Regression baseline does not exist: {path}. "
                f"Set {UPDATE_BASELINE_ENV}=true to create it intentionally."
            )
        path.write_text(json.dumps(current, indent=2, sort_keys=True))
        return BaselineComparison(
            baseline_path=path,
            current=current,
            expected=current,
            differences=[],
            updated=True,
        )

    expected = json.loads(path.read_text())
    differences = diff_snapshots(expected, current)
    return BaselineComparison(
        baseline_path=path,
        current=current,
        expected=expected,
        differences=differences,
    )


def diff_snapshots(
    expected: Any,
    current: Any,
    path: str = "$",
) -> list[str]:
    if type(expected) is not type(current):
        return [
            f"{path}: type changed from {type(expected).__name__} "
            f"to {type(current).__name__}"
        ]

    if isinstance(expected, dict):
        differences: list[str] = []
        expected_keys = set(expected)
        current_keys = set(current)
        for key in sorted(expected_keys - current_keys):
            differences.append(f"{path}.{key}: expected key disappeared")
        for key in sorted(current_keys - expected_keys):
            differences.append(f"{path}.{key}: unexpected key appeared")
        for key in sorted(expected_keys & current_keys):
            differences.extend(diff_snapshots(expected[key], current[key], f"{path}.{key}"))
        return differences

    if isinstance(expected, list):
        differences = []
        if len(expected) != len(current):
            differences.append(
                f"{path}: length changed from {len(expected)} to {len(current)}"
            )
        for index, (expected_item, current_item) in enumerate(zip(expected, current)):
            differences.extend(
                diff_snapshots(expected_item, current_item, f"{path}[{index}]")
            )
        return differences

    if expected != current:
        return [f"{path}: expected {expected!r}, got {current!r}"]
    return []


def _json_normalize(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, sort_keys=True))
