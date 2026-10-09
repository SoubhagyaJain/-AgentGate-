# Architecture decisions

## 001 — Root and scope (2026-10-09)
Decision: use the existing workspace as repository root; implement Phase 1 only.
Reason: workspace is empty and the latest user request narrows authorization.
Alternatives: nested AgentGate folder, full seven-phase implementation.
Consequences: no duplicate project root; later work requires new authorization.
Modules: whole repository; docs/PROJECT_SPEC.md.

## 002 — Minimal dependencies and packaging (2026-10-09)
Decision: src layout, uv lock, Pydantic runtime, pytest dev, stdlib HTTP.
Reason: strict boundaries and reproducible Windows setup without frameworks.
Alternatives: OpenAI SDK, requests, agent frameworks.
Consequences: explicit small adapter and transport protocol; no dotenv loading.
Modules: pyproject.toml, config.py, llm_client.py.

## 003 — Strict trust boundaries (2026-10-09)
Decision: immutable domain models, exact cents as Decimal/string, duplicate-key
JSON rejection, credentials excluded from config serialization. Provider metadata
may evolve; retain complete raw provider text while parsing known fields.
Reason: prevent coercion, ambiguous arguments and secret leakage without rigidly
rejecting harmless new provider metadata. Loopback HTTP only; hosted HTTPS and
explicit keys. Redirects will be disabled in the adapter.
Alternatives: floats, coercive models, serializing credentials.
Consequences: issue_refund amount must be a two-decimal JSON string.
Modules: schemas.py, config.py, exceptions.py.

## 004 — Interpreter and pytest cache (2026-10-09)
Decision: .python-version pins 3.12; disable optional pytest cache plugin.
Reason: uv initially selected 3.13; target verification is 3.12. OneDrive denied
pytest's cache-directory rename; tests require no cache and none is relied upon.
Alternatives: alternate external cache directory, ignoring the warning.
Consequences: deterministic tests run cache-free; no production behavior change.
Modules: .python-version, pyproject.toml.

## 005 — Tax/refund semantics and access privacy (2026-10-09)
Decision: restocking applies to discounted item value, rounded half up; item tax
refund is prorated by the remaining item value and rounded half up. Shipping is
untaxed separately in the synthetic data. A zero-value refund is ineligible.
Unknown, foreign and unverified order lookups share the same refusal.
Reason: explicit independently testable amounts without order-existence leaks.
Alternatives: subtract fee while refunding full tax; distinguish missing orders.
Consequences: opened 1043 refunds 79.19; day 30 qualifies, day 31 does not.
Modules: schemas.py, data/fixtures, tools/orders.py, tools/refunds.py.

## 006 — Duplicate issuance denied (2026-10-09)
Decision: deny a second issue_refund, even when amount matches. Calculations and
receipts are case-local; session consent is immutable and order-scoped.
Reason: latest Phase 1 specification requires no prior successful issuance.
Alternatives: return existing receipt as an idempotent success (master plan allowed it).
Consequences: one execution/state change; later duplicate produces a denial.
Modules: tools/state.py, tools/refunds.py, tools/registry.py.

## 007 — Adapter retries and runtime limits (2026-10-09)
Decision: non-streaming urllib, redirects disabled, bounded responses, max two
transient HTTP retries per turn. Record raw attempts and parsed responses as
different events. Reject duplicate IDs/truncated completions and batches exceeding
remaining budget before any call in that batch executes. One final-answer repair
shares the eight-turn budget. Tool attempts, including invalid ones, consume budget.
Reason: protect credentials and avoid ambiguous/discarded executions or refund replay.
Alternatives: retry full agent turns, partial batch execution, unbounded repairs.
Consequences: infrastructure failures retain prior effects and entire observable trace.
Modules: llm_client.py, agent.py, schemas.py.

## 008 — Structured grounded response and test labeling (2026-10-09)
Decision: validate every typed claim against each cited retrieved evidence, then
render using deterministic templates. Validate eligibility/receipt outcome bindings.
Injected transports are always labeled test_transport; no live-pass inference.
Reason: no semantic judge required for Phase 1; completion is not evaluation success.
Alternatives: unconstrained prose, hidden scripted fallback, scenario scoring now.
Consequences: later evaluator still checks required tool paths and task expectations.
Known credential text is redacted in raw responses; Ollama's ignored placeholder is not.
Modules: answers.py, agent.py, llm_client.py, tests/support.py.

## 009 — Minimal operator CLI and artifact publication (2026-10-09)
Decision: add one-request CLI and no-network validate-only; trusted session is an
explicit operator file, safe example unverified/without consent. No evaluator shim.
Persist unique immutable traces using atomic exclusive same-filesystem hard links.
Reason: demonstrate the real runtime interface without claiming Phase 2 or live execution.
Alternatives: Python API only; overwriting reports; bundling a fake evaluate command.
Consequences: fixture/prompt paths are external repository assets; existing output
is refused before network. CLI 0=structural completion, 2=incomplete request,
3=input/artifact failure. Unsupported filesystems fail explicitly; Windows/OneDrive
publication verified. Runtime traces are in-memory until run completion.
Modules: __main__.py, telemetry/traces.py, README.md, data/fixtures/session.example.json.
