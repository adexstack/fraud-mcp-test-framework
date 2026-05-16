"""Evidence capture helpers for PTB/PTO readiness."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPORTS_DIR = Path("reports")
SENSITIVE_FIELD_NAMES = {
    "auth",
    "authorization",
    "auth_token",
    "api_key",
    "bearer",
    "cookie",
    "mcp_auth_token",
    "password",
    "secret",
    "token",
}
REDACTED = "[REDACTED]"


@dataclass
class EvidenceRecord:
    name: str
    payload: dict[str, Any]
    captured_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    evidence_type: str = "test_evidence"

    def as_dict(self) -> dict[str, Any]:
        return sanitize_payload(asdict(self))


class EvidenceWriter:
    """Writes machine-readable test evidence under reports/."""

    def __init__(
        self,
        base_dir: Path | None = None,
        reports_dir: Path = REPORTS_DIR,
    ) -> None:
        self.reports_dir = reports_dir
        self.base_dir = base_dir or reports_dir / "evidence"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.reports_dir / "evidence.jsonl"

    def write_json(self, name: str, payload: dict[str, Any]) -> Path:
        record = EvidenceRecord(name=name, payload=payload)
        sanitized = record.as_dict()
        path = self.base_dir / f"{_safe_name(name)}.json"
        path.write_text(json.dumps(sanitized, indent=2, sort_keys=True))
        self.write_jsonl(name, payload)
        return path

    def write_jsonl(self, name: str, payload: dict[str, Any]) -> Path:
        record = EvidenceRecord(name=name, payload=payload)
        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.as_dict(), sort_keys=True) + "\n")
        return self.jsonl_path


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                sanitized[key] = REDACTED
            else:
                sanitized[key] = sanitize_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_payload(item) for item in value)
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(sensitive in normalized for sensitive in SENSITIVE_FIELD_NAMES)


def _safe_name(name: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in name)
