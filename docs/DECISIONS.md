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
