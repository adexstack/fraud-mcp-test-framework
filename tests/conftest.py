from __future__ import annotations

import json
from importlib import resources
from typing import Any

import pytest

from fraud_mcp_tests.config import McpTestConfig, load_config
from fraud_mcp_tests.evidence import EvidenceWriter
from fraud_mcp_tests.mcp_client import McpClient
from fraud_mcp_tests.schemas.expected_tools import EXPECTED_TOOL_NAMES
from fraud_mcp_tests.trace import TraceRecorder


@pytest.fixture(scope="session")
def mcp_config() -> McpTestConfig:
    return load_config()


@pytest.fixture
def trace_recorder(request: pytest.FixtureRequest) -> TraceRecorder:
    return TraceRecorder(test_name=request.node.nodeid)


@pytest.fixture
def evidence_writer() -> EvidenceWriter:
    return EvidenceWriter()


@pytest.fixture(scope="session")
def transaction_testdata() -> list[dict[str, Any]]:
    return _load_testdata("transactions.json")


@pytest.fixture(scope="session")
def customer_testdata() -> list[dict[str, Any]]:
    return _load_testdata("customers.json")


@pytest.fixture(scope="session")
def workflow_scenarios() -> dict[str, Any]:
    loaded = _load_testdata_object("workflow_scenarios.json")
    assert isinstance(loaded, dict), "workflow_scenarios.json must contain a JSON object"
    return loaded


@pytest.fixture(scope="session")
def rbac_matrix() -> dict[str, Any]:
    loaded = _load_testdata_object("rbac_matrix.json")
    assert isinstance(loaded, dict), "rbac_matrix.json must contain a JSON object"
    return loaded


@pytest.fixture(scope="session")
def minimal_tool_payloads() -> dict[str, dict[str, object]]:
    return {
        "search_customer": {"customer_id": "cust_001"},
        "get_transaction": {"transaction_id": "txn_001"},
        "score_transaction_risk": {"transaction_id": "txn_001"},
        "create_fraud_case": {"transaction_id": "txn_001"},
        "get_case_status": {"case_id": "case_001"},
        "escalate_case": {
            "case_id": "case_001",
            "reason": "Manual review required",
        },
        "generate_investigation_summary": {"case_id": "case_001"},
    }


@pytest.fixture(scope="session", params=EXPECTED_TOOL_NAMES)
def expected_tool_name(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture
def mcp_client(
    mcp_config: McpTestConfig,
    trace_recorder: TraceRecorder,
) -> McpClient:
    if not mcp_config.is_configured:
        pytest.skip("MCP_SERVER_URL is not configured")

    with McpClient(mcp_config, trace_recorder=trace_recorder) as client:
        yield client


def _load_testdata(filename: str) -> list[dict[str, Any]]:
    data_file = resources.files("fraud_mcp_tests.testdata").joinpath(filename)
    loaded = json.loads(data_file.read_text())
    assert isinstance(loaded, list), f"{filename} must contain a JSON list"
    return loaded


def _load_testdata_object(filename: str) -> Any:
    data_file = resources.files("fraud_mcp_tests.testdata").joinpath(filename)
    return json.loads(data_file.read_text())
