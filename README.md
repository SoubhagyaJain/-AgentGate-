# AgentGate — Can a Prompt Change Break Production?

Phase 1 implements deterministic foundations for a synthetic support agent.
The seven-phase experiment specification lives in `docs/PROJECT_SPEC.md`.
Current verification and resume instructions are in `docs/HANDOFF.md`.

## Setup

Python 3.12+ and uv are required for the documented workflow:

```powershell
uv sync --locked
uv run --locked python -m pytest -q
```

Runtime dependency: Pydantic. Development dependency: pytest. The HTTP adapter
uses Python's standard library. No LLM server is needed for deterministic tests.
`.env.example` documents environment variables; copy values into your process
environment rather than expecting automatic dotenv loading.

Live Ollama/hosted execution has **not been verified**. The later model target
is `qwen3.5:4b-q4_K_M`. No mock result may be labeled live evaluation.

See `AGENTS.md` before development. Phase 2 is not currently authorized.
