# Fraud MCP Test Framework - Codex Instructions

You are working on `fraud-mcp-test-framework`, an independent QA/SDET validation framework for an external Fraud Detection MCP server.

The MCP server under test is a separate project:

```text
/Users/bola/seyi/AI-LLM/fraud-mcp-platform

This test framework must treat the MCP server as a black-box external system. Do not import implementation code from the MCP server. Interact with it only through MCP/server-facing interfaces, configured URLs, fixtures, traces, and tool responses.

Project Purpose

This framework validates an AI-enabled Fraud Detection MCP platform from the perspective of an AI Quality Engineer / SDET.

It is designed to test:

MCP server connectivity
MCP tool discovery
tool schema correctness
tool invocation behaviour
response contracts
fraud business-rule correctness
risk-score accuracy
workflow orchestration
stateful multi-step investigations
negative inputs and tool misuse
hallucination and grounding controls
RBAC/security boundaries
latency and observability
trace capture and auditability
regression impact
PTB/PTO evidence readiness
optional RAGAS-based evaluation for generated natural-language responses

The framework should demonstrate enterprise-grade AI Quality Engineering for MCP tools, Skills, agentic behaviours, and financial-crime workflows.

Core Engineering Principles

Follow these principles strictly:

Do not rewrite the existing framework unnecessarily.
Do not break currently passing tests.
Prefer small, incremental changes.
Keep deterministic pytest tests as the primary regression suite.
Keep RAGAS tests optional and disabled by default.
Avoid large refactors unless explicitly requested.
Reuse existing fixtures, MCP client abstractions, trace utilities, evidence utilities, and reporting utilities where available.
Keep test logic readable and interview-friendly.
Tests should produce clear evidence and actionable failure messages.
Treat the MCP server as an external system under test.
Architecture Expectations

Maintain a layered test framework structure.

Preferred module responsibilities:

src/fraud_mcp_tests/config.py
  Loads environment-driven settings.

src/fraud_mcp_tests/mcp_client.py
  Provides MCP client abstraction and tool invocation support.

src/fraud_mcp_tests/assertions.py
  Reusable assertion helpers.

src/fraud_mcp_tests/trace.py
  Captures tool-call and workflow traces.

src/fraud_mcp_tests/evidence.py
  Writes test evidence for PTB/PTO and audit review.

src/fraud_mcp_tests/reporting.py
  Produces summary reports.

src/fraud_mcp_tests/schemas/
  Expected MCP tool inventory, input contracts, and response contracts.

src/fraud_mcp_tests/ragas_eval/
  Optional RAGAS evaluation layer for generated natural-language responses.

Do not mix MCP client logic, assertion logic, RAGAS evaluation logic, and report writing into the same file.

Existing Test Categories

Preserve the existing test categories where possible:

tests/connection/
tests/contracts/
tests/correctness/
tests/workflows/
tests/safety/
tests/security/
tests/observability/
tests/governance/

RAGAS tests should be added separately under:

tests/ragas/

Reports should be written under:

reports/

RAGAS reports should be written under:

reports/ragas/
Pytest Markers

Use clear pytest markers.

Expected markers include:

connection
discovery
contract
invocation
correctness
workflow
stateful
safety
security
observability
governance
regression
live
ragas
llm_eval

RAGAS tests must be marked with:

@pytest.mark.ragas
@pytest.mark.llm_eval

If they require a running MCP server, also mark them with:

@pytest.mark.live
RAGAS Integration Rules

RAGAS must be introduced as an optional evaluation layer, not as a replacement for deterministic tests.

Use RAGAS only where LLM-style evaluation adds value, especially:

investigation summary faithfulness
response relevancy
factual consistency against MCP tool evidence
policy grounding
natural-language fraud investigation summaries
agentic workflow quality where appropriate

Do not use RAGAS for deterministic checks such as:

tool exists
required field exists
schema type matches
risk score is between 0 and 100
case status changed correctly
RBAC permission denied correctly
latency threshold is met
structured error response is returned

Those should remain normal pytest assertions.

RAGAS Configuration

RAGAS must be disabled by default.

Add or preserve these environment variables:

RAGAS_ENABLED=false
RAGAS_MODEL=gpt-4o-mini
RAGAS_FAITHFULNESS_THRESHOLD=0.80
RAGAS_RESPONSE_RELEVANCY_THRESHOLD=0.75
RAGAS_FACTUAL_CORRECTNESS_THRESHOLD=0.75
AGENT_TOOL_CALL_F1_THRESHOLD=0.90

If RAGAS_ENABLED=false, RAGAS tests should skip cleanly.

If OPENAI_API_KEY is missing, RAGAS tests should skip cleanly.

Do not make normal regression test runs depend on OpenAI, RAGAS, or external LLM calls.

RAGAS Design Pattern

Use MCP tool outputs as grounding context.

For example, an investigation summary evaluation should use:

user_input:
  "Summarise the fraud investigation for transaction TXN-CRIT-001"

response:
  The generated investigation summary from the MCP server.

contexts:
  - transaction details returned by get_transaction
  - risk assessment returned by score_transaction_risk
  - case details returned by create_fraud_case
  - escalation details returned by escalate_case

reference:
  Expected high-level summary guidance, where available.

The goal is to check whether generated MCP responses are grounded in actual tool-derived evidence.

RAGAS Module Expectations

If adding RAGAS support, use this structure:

src/fraud_mcp_tests/ragas_eval/
  __init__.py
  adapters.py
  datasets.py
  metrics.py
  evaluators.py

Expected responsibilities:

adapters.py
  Converts MCP outputs, traces, and workflow evidence into RAGAS-compatible samples.

datasets.py
  Provides small sample builders or dataset helpers.

metrics.py
  Defines supported RAGAS metrics and fallback metric logic.

evaluators.py
  Runs RAGAS evaluation and returns structured results.

RAGAS reports should include:

{
  "metric_name": "faithfulness",
  "score": 0.84,
  "threshold": 0.80,
  "passed": true,
  "reason": "Optional explanation where available"
}
Agentic Workflow Evaluation

For workflow evaluation, prefer deterministic tool-sequence validation first.

Expected fraud investigation workflow:

1. get_transaction
2. score_transaction_risk
3. create_fraud_case
4. escalate_case
5. generate_investigation_summary

Capture or derive:

expected_tools
actual_tools
missing_tools
unexpected_tools
tool_call_precision
tool_call_recall
tool_call_f1
exact_sequence_match

If the installed RAGAS version supports relevant agent/tool-use metrics cleanly, integrate them.

If not, implement a deterministic local fallback and document it clearly.

PTB/PTO Evidence Expectations

The framework should support Permit to Build and Permit to Operate style evidence.

PTB evidence should cover:

MCP server reachable
expected tools discoverable
schemas/contracts valid
core business rules passing
safety tests present
security/RBAC tests present where supported
trace capture enabled

PTO evidence should cover:

end-to-end workflow tests passing
audit evidence generated
latency within threshold
regression baseline stable
no critical safety failures
optional RAGAS evaluation results where enabled

RAGAS evidence may be included in governance summaries but should not block default fast regression unless explicitly enabled.

Error Handling Expectations

Tests should fail clearly and use evidence-oriented failure messages.

Good failure message:

Expected generate_investigation_summary to remain grounded in transaction TXN-CRIT-001 evidence, but response referenced an unknown transaction ID.

Poor failure message:

AssertionError

All failed MCP calls should expose enough diagnostic information to debug:

tool name
input arguments, sanitised where needed
response/error
latency
trace ID or local trace ID
timestamp

Do not expose secrets in logs, reports, or trace files.

Security and Safety Expectations

When adding or updating safety tests, validate:

missing required inputs
invalid IDs
wrong argument types
extra arguments
long strings
prompt-injection-like inputs
SQL-injection-like inputs
path traversal-like inputs
unsafe state mutation
internal error leakage
role/permission boundary failures

Safety tests should assert that the MCP server:

does not crash
returns structured errors
avoids leaking internals
avoids unsafe state mutation
remains auditable
Coding Style

Use:

Python 3.11+
pytest
type hints
small functions
clear fixtures
readable assertions
environment-driven config
JSON/JSONL evidence files
minimal dependencies

Avoid:

large monolithic test files
hidden global state
hardcoded absolute URLs
hardcoded secrets
importing server internals from fraud-mcp-platform
duplicating fraud server implementation logic inside the test framework
excessive mocking for live MCP tests
Test Execution Expectations

Before completing work, run the appropriate tests.

Default regression:

uv run pytest -m "not ragas and not llm_eval"

Full local suite with RAGAS disabled:

RAGAS_ENABLED=false uv run pytest

RAGAS-only tests, when explicitly enabled:

RAGAS_ENABLED=true uv run pytest tests/ragas -m ragas

If a live MCP server is required, make sure tests skip cleanly when MCP_SERVER_URL is not configured or the server is unavailable.

Do not make offline/unit tests depend on a running MCP server.

README Expectations

When adding new capabilities, update the README briefly.

For RAGAS integration, explain:

why RAGAS is used selectively
what RAGAS evaluates
what deterministic pytest still owns
how to enable RAGAS tests
how RAGAS evidence supports PTB/PTO
how reports are generated

Keep README updates concise and practical.

Current Implementation Constraint

This is an existing working project.

When implementing new requests:

Inspect the existing project first.
Identify existing config, fixtures, client, trace, evidence, and reporting utilities.
Reuse what already exists.
Add the smallest safe extension.
Do not rename or move existing files unless required.
Do not rewrite passing tests.
Preserve backward compatibility.
Run tests after changes.