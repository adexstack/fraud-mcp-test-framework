# Fraud MCP Test Framework

Independent pytest-based validation framework for an external Fraud Detection MCP
server. The server is treated as a black-box system under test.

## Scope

This scaffold focuses on:

- Environment-based configuration
- MCP client abstraction
- Pytest fixtures
- Connection and initialize validation
- Tool discovery validation
- Advertised tool input schema contract checks
- Evidence and trace capture helpers

Business rule, fraud scoring, orchestration, RBAC, safety, and governance tests
will be added in later layers.

## Configuration

Copy `.env.example` to `.env` or export these variables:

```sh
MCP_SERVER_URL=https://fraud-mcp-platform.onrender.com/mcp
MCP_TRANSPORT=streamable-http
MCP_AUTH_TOKEN=
MCP_TIMEOUT_SECONDS=30
RAGAS_ENABLED=false
RAGAS_MODEL=gpt-4o-mini
RAGAS_FAITHFULNESS_THRESHOLD=0.80
RAGAS_RESPONSE_RELEVANCY_THRESHOLD=0.75
RAGAS_FACTUAL_CORRECTNESS_THRESHOLD=0.75
AGENT_TOOL_CALL_F1_THRESHOLD=0.90
AGENT_GOAL_SUCCESS_THRESHOLD=0.85
```

The framework defaults to the hosted streamable HTTP Fraud MCP endpoint above.
Set `MCP_SERVER_URL` to point the same tests at another MCP server.

Supported transports in this first version:

- `http`
- `streamable-http`

## Running Tests

```sh
uv run pytest
```

This runs the whole pytest collection. With `RAGAS_ENABLED=false`, RAGAS live
evaluation tests are collected but skip cleanly. A normal local result may look
like `142 passed, 4 skipped`: the skipped tests are the optional RAGAS
LLM-as-judge tests waiting for explicit enablement.

Useful marker selections:

```sh
uv run pytest -m connection
uv run pytest -m discovery
uv run pytest -m contract
uv run pytest -m governance
```

## Test Runbook

Use these commands depending on what you are trying to prove.

| Situation | Command | Expected result |
| --- | --- | --- |
| Quick deterministic CI safety net | `uv run pytest -m "not live and not ragas and not llm_eval" -ra` | Fastest core regression. No live MCP calls and no RAGAS judge calls. |
| Normal local regression with RAGAS disabled | `uv run pytest -v` | Runs deterministic and live-marked tests against configured/default MCP settings; RAGAS tests skip with `RAGAS_ENABLED is not true`. |
| Full non-RAGAS regression | `uv run pytest -m "not ragas and not llm_eval" -ra` | Recommended before commits. RAGAS tests are deselected, so optional LLM evaluation cannot affect the result. |
| RAGAS unit/scaffold checks only | `uv run pytest tests/unit/test_config.py tests/ragas -ra` | Adapter/evaluator/config tests pass; live RAGAS tests skip unless explicitly enabled. |
| Live MCP integration only | `uv run pytest -m "live and not ragas and not llm_eval" -ra` | Exercises the configured MCP server using normal pytest assertions. Requires `MCP_SERVER_URL` or skips where unavailable. |
| Optional RAGAS evaluation | `RAGAS_ENABLED=true uv run pytest tests/ragas -m ragas -ra` | Runs LLM-as-judge evaluation. Also requires `OPENAI_API_KEY`; missing key skips clearly. |
| Governance/PTB/PTO evidence | `uv run pytest tests/governance -ra` | Regenerates/validates governance evidence including the optional RAGAS evidence block. |
| Lint | `uv run ruff check .` | Static style check should pass before commit. |

Recommended day-to-day flow:

1. Run `uv run pytest -m "not ragas and not llm_eval" -ra`.
2. Run `uv run ruff check .`.
3. For release evidence, run `uv run pytest tests/governance -ra`.
4. For optional LLM quality evidence, set `RAGAS_ENABLED=true` and
   `OPENAI_API_KEY`, then run `uv run pytest tests/ragas -m ragas -ra`.

Interpreting common output:

- `skipped ... RAGAS_ENABLED is not true`: expected when RAGAS is disabled.
- `skipped ... OPENAI_API_KEY is not configured`: expected when RAGAS is enabled
  but no judge model credential is available.
- `deselected`: expected when using marker expressions such as
  `-m "not ragas and not llm_eval"`.
- Report files under `reports/evidence/` and `reports/governance_summary.json`
  may be rewritten by live/governance runs. Review those diffs intentionally
  before committing generated evidence.

## Test Pyramid

Level 1 is deterministic pytest validation: fast, cheap checks for schemas,
contracts, business rules, RBAC policy shape, latency capture logic, and local
governance evidence. These should be the default CI safety net:

```sh
uv run pytest -m "not live and not ragas and not llm_eval"
```

Level 2 is live MCP integration validation. These tests exercise the configured
MCP server through `MCP_SERVER_URL` and remain normal pytest assertions:

```sh
uv run pytest -m "live and not ragas and not llm_eval"
```

Level 3 is optional RAGAS evaluation. These are slower LLM-as-judge checks for
generated MCP responses and agentic workflow quality, intended for release
evidence and PTB/PTO support:

```sh
RAGAS_ENABLED=true uv run pytest -m ragas
```

Start RAGAS thresholds at realistic, non-flaky values: `0.80` for faithfulness,
`0.75` for response relevancy and factual correctness, `0.90` for agent
tool-call F1, and `0.85` for agent goal success. Deterministic workflow tests
should still expect exact behaviour, such as an exact sequence match and local
workflow F1 of `1.0`.

## RAGAS Evaluation Layer

This framework includes an optional RAGAS-based evaluation layer for
MCP-generated natural language responses.

The deterministic pytest suite validates MCP contracts, tool invocation,
business rules, state transitions, safety boundaries, RBAC, latency, and
auditability.

RAGAS is used only where LLM-style evaluation is appropriate, especially:

- investigation summary faithfulness
- response relevancy
- policy grounding
- factual consistency against MCP tool evidence
- agentic workflow/tool-call quality where supported

The RAGAS evaluation uses MCP tool outputs as grounding context. This allows
generated summaries to be assessed against actual transaction, risk, case, and
escalation evidence. Those `retrieved_contexts` are MCP tool outputs, not vector
database chunks. RAGAS is not used to test every MCP tool.

RAGAS tests are marked as:

- `ragas`
- `llm_eval`
- `live`

They are disabled by default for fast local and CI regression runs.

To run:

```bash
RAGAS_ENABLED=true uv run pytest tests/ragas -m ragas
```

Keep deterministic checks in normal pytest, including field presence such as
`customer_id`, `transaction_id`, `risk_score`, and `case_id`; risk-score bounds;
case status transitions; RBAC failure responses; latency thresholds; and schema
validation. RAGAS sits above those checks as a qualitative evaluation layer.

Example RAGAS row shape:

```json
{
  "user_input": "Summarise the fraud investigation for transaction TXN-CRIT-001",
  "response": "The transaction TXN-CRIT-001 was assessed as CRITICAL...",
  "retrieved_contexts": [
    "Transaction TXN-CRIT-001 amount is 25000 GBP...",
    "Risk assessment score is 95 with signals: high amount, PEP, new beneficiary...",
    "Case CASE-001 status is ESCALATED..."
  ],
  "reference": "The summary should state the transaction risk level, case status, and escalation reason without claiming proven fraud."
}
```

The evaluator wrapper skips cleanly when `RAGAS_ENABLED=false`, when
`OPENAI_API_KEY` is not configured, or when the installed RAGAS version does not
expose a requested optional metric. RAGAS outputs should be written under
`reports/ragas/`.

## Regression Baselines

Regression impact tests compare current MCP behaviour against JSON snapshots in
`reports/baselines/`.

Create or intentionally refresh baselines with:

```sh
UPDATE_BASELINE=true uv run pytest tests/governance
```

Normal runs fail on unexpected drift, including missing expected tools, required
schema changes, known risk outcome changes, workflow state transition changes,
or latency that exceeds the configured timeout threshold.

## Project Layout

```text
src/fraud_mcp_tests/
  config.py
  mcp_client.py
  assertions.py
  evidence.py
  trace.py
  reporting.py
  ragas_eval/
  schemas/
    expected_tools.py
    tool_contracts.py
tests/
  connection/
  contracts/
  ragas/
```

Evidence files are written under `reports/evidence/` during live integration
runs.

## Adding Contracts Later

Add agreed tool names to `src/fraud_mcp_tests/schemas/expected_tools.py`.
Add response JSON Schemas to `src/fraud_mcp_tests/schemas/tool_contracts.py`.
