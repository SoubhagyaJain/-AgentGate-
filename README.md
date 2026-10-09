# AgentGate — Can a Prompt Change Break Production?

Phase 1 is implemented: four synthetic tools, strict authorization, a bounded
model-driven runtime, structured grounded answers, and inspectable JSON traces.
There is no 50-case evaluator, quality gate or CI workflow yet. The seven-phase
master plan is preserved in `docs/PROJECT_SPEC.md`; the current resume checkpoint
is `docs/HANDOFF.md`. Development is limited to Phase 1 until further authorization.

## Setup

Python 3.12+ and uv are required for the documented workflow:

```powershell
uv sync --locked
uv run --locked python -m pytest -q
uv run --locked python -m compileall -q src
uv build
```

Runtime dependency: Pydantic. Development dependency: pytest. The HTTP adapter
uses Python's standard library. No LLM server is needed for deterministic tests.
The lock file pins all installed dependencies; `.python-version` selects 3.12.
Wheels contain the Python package. Fixtures and prompts remain repository assets;
pass their explicit paths when invoking an installed wheel outside the checkout.
`.env.example` documents environment variables; copy values into your process
environment rather than expecting automatic dotenv loading.

## Deterministic validation and optional single-request execution

Validate inputs without contacting any model:

```powershell
uv run --locked python -m agentgate "Can I get a refund for 1042?" --session data/fixtures/session.example.json --validate-only
```

After an operator configures a real compatible endpoint, the same command
without `--validate-only` performs one genuine model-driven request:

```powershell
$env:AGENTGATE_BASE_URL = "http://localhost:11434/v1"
$env:AGENTGATE_MODEL = "qwen3.5:4b-q4_K_M"
$env:AGENTGATE_API_KEY = "ollama"
uv run --locked python -m agentgate "Can I get a refund for 1042?" --session data/fixtures/session.example.json --output reports/request.json
```

The example session is intentionally unverified and has no refund consent.
Sessions/fixtures are **trusted operator inputs**, never end-user uploads or
fields inferred from conversation text. In tests, verified sessions and consent
are constructed directly from trusted fixtures. There is no real authentication
or finance integration. No model installation is part of Phase 1.

CLI options: `--session` (required), `--fixtures`, `--prompt`, `--output`, and
`--validate-only`. Configuration reads `AGENTGATE_MODEL`, `BASE_URL`, `API_KEY`,
`TIMEOUT`, `TEMPERATURE`, `TOP_P`, `PRESENCE_PENALTY`, `FREQUENCY_PENALTY`,
`MAX_TOKENS`, `MAX_TURNS`, `MAX_TOOL_INVOCATIONS`, `SEED`, and `REASONING_EFFORT`
with the `AGENTGATE_` prefix on every variable. Defaults are recorded in each
trace; optional provider fields are omitted unless configured. Hosted endpoints
require HTTPS and an explicit key; only loopback accepts HTTP. Redirects are refused.

CLI exit codes: `0` means structurally completed (or validation-only succeeded),
`2` means an incomplete model request with an inspectable trace, and `3` means
invalid inputs/configuration or failed trace persistence. Existing output files
are refused. **Completion is not a quality/evaluation pass.** The later master-plan
`agentgate.evaluate` and `agentgate.gate` commands are intentionally not implemented.

## Business rules and independent checks

The evaluation date is fixed at **2026-10-09**, independent of machine time.
All amounts are nonnegative two-decimal strings at JSON boundaries and Decimal
internally. Synthetic shipping excludes shipping tax.

- Unshipped cancellation: discounted item price + paid item tax + shipping.
- Delivered physical return: eligible through day 30 inclusive from delivery.
- Opened nondefective goods: deduct 20% of discounted item price, rounded half up.
- Item tax: refund the paid tax in proportion to the remaining item value,
  rounded half up to cents. No deduction on defective goods.
- Standard delivered shipping is nonrefundable; in-transit goods are ineligible.
- Redeemed digital goods are ineligible; unredeemed delivered goods use the same
  return window without a restocking deduction. Zero-value refunds are ineligible.

Independent test expectations include order 1042 returning **99.00**, opened
1043 returning **79.19** (18.00 deduction and 7.20 tax refund), and unshipped 1046
returning **93.00**. The tests also cover exact half-cent tax rounding and days
30/31. Fixtures reject rule/fact conflicts, duplicate IDs and future order dates.

## Runtime, security and traces

The model chooses tools; the registry validates names/arguments before dispatch.
Order reads and calculations require verified ownership. Issuance additionally
requires trusted order-scoped consent, an eligible prior calculation, exact
amount, and no prior receipt. Duplicate issuance is denied. Missing and foreign
orders return identical refusals, with no private data or existence disclosure.

Execution is sequential and case-local: eight model turns, twelve attempted
tool invocations, one final-answer repair inside the turn budget, and at most
two retries of transient HTTP failures. A batch exceeding remaining capacity
is rejected as a whole. Reused call IDs and truncated completions are rejected.
Completed tools are never replayed to recover a later HTTP request.

Final answers contain an outcome and typed claims with evidence references.
Every cited reference must support that claim; eligible/ineligible outcomes need
matching eligibility claims, and refund issuance needs an actual simulated
receipt. The response is rendered deterministically. Required retrieval/order
paths, user-task completion and safety grading remain Phase 2 evaluator work.

JSON trajectories preserve raw provider responses (with known credential text
redacted), parsed completions, message history, tool calls/results, evidence,
errors, retry attempts, distinct attempted/denied/executed/state-change events,
usage when available, per-step latency and total latency. Missing usage is null.
Original/effective prompts, fixtures, configuration and tool definitions have
hashes. Full configuration excludes the credential; headers are never recorded.

Trace files are immutable and atomically published using a same-filesystem hard
link; verified on this Windows/OneDrive workspace. Unsupported filesystems fail
explicitly. Runtime traces stay in memory until the request returns; killing a
process can lose an in-flight trace. Repository development checkpoints are
independent of runtime trace persistence.

## Verification and limitations

The deterministic suite currently contains **124 passing tests** on Python
3.12.10. Scripted transports exist only under tests and all injected transports
are labeled `test_transport`. A localhost HTTP stub tests the actual urllib wire
protocol and redirect refusal; it is not an LLM. The transport label alone is
not an independent attestation of an endpoint's model authenticity.

The source distribution and wheel build successfully; the wheel has also been
installed/imported in an isolated environment. Optional pytest cache is disabled
because OneDrive denied its initial directory rename; tests now run warning-free.

Live Ollama/hosted execution has **not been performed or verified**. RTX 4050
memory fit, model tool support, thinking controls, context sizing and performance
remain Phase 3 checks. No live result or prompt-regression conclusion is claimed.

See `AGENTS.md` before development. Every session must reconcile the specification,
progress, handoff and decisions with Git/source state, rerun existing tests, and
checkpoint coherent milestones locally. Phase 2 is not currently authorized.
