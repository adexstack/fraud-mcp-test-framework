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

Useful marker selections:

```sh
uv run pytest -m connection
uv run pytest -m discovery
uv run pytest -m contract
uv run pytest -m governance
```

## Optional RAGAS Evaluations

RAGAS tests live under `tests/ragas/` and are marked with `ragas` and
`llm_eval`. They are optional LLM-as-judge evaluations for answer quality
signals such as faithfulness, response relevancy, and factual correctness.
Deterministic pytest checks still own contracts, schemas, workflows, RBAC,
latency, and regression drift. RAGAS is disabled by default and is not part of
the default fast regression path.

Enable them explicitly with:

```sh
RAGAS_ENABLED=true uv run pytest -m ragas
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
