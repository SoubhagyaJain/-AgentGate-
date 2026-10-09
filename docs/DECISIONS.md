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
