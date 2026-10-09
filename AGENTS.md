# AgentGate coding-agent entry point

Every new coding session MUST read, in order: `docs/PROJECT_SPEC.md`,
`docs/PROGRESS.md`, `docs/HANDOFF.md`, and `docs/DECISIONS.md`. Then inspect the
actual files, `git status --short --branch`, and recent commits, and run the
appropriate existing tests. Reconcile discrepancies before changing code.
Resume the first authorized incomplete task; never recreate working modules.

## Scope and architecture

The current authorization is **Phase 1 only**. Do not implement the 50-case
dataset, evaluator, live experiment, CI workflows, or install/pull Ollama without
new authorization. The permanent seven-phase specification is in PROJECT_SPEC;
the supplied Phase 1 request is retained in `docs/PHASE1_REQUEST.md`.

Use Python 3.12+, `src/agentgate`, Pydantic runtime schemas, pytest, uv, and the
standard library. No frameworks, databases, frontend, additional agents, or LLM
judges. Tools operate exclusively on synthetic case-local state.

## Engineering rules

- Validate external input before dispatch; never trust model-produced identity,
  authorization, consent, tool names, monetary values, or claims.
- Use immutable trusted sessions/policies/orders and Decimal money. No real
  payments. Do not expose existence or data of inaccessible orders.
- Separate model-visible messages from trace/evaluator metadata and secrets.
- No production scripted model, automatic mock fallback, or claimed live pass.
- Preserve raw observable outputs, IDs, errors, retries, denial and execution
  events. Do not manufacture hidden reasoning or claim to capture it.
- Keep modules small and typed. Tests must use independent expected outcomes,
  meaningful counterexamples, and scripted HTTP transports only in tests.
- Never weaken requirements solely to make tests pass.

## Commands (PowerShell, workspace root)

```powershell
uv sync --locked
uv run --locked python -m pytest -q
uv run --locked python -m compileall -q src
git status --short --branch
git log -5 --oneline
```

## Mandatory checkpoints

Before complex work update HANDOFF with the immediate objective. After each
coherent milestone save source, run relevant tests, update PROGRESS and HANDOFF,
record meaningful decisions, append actual evidence to SESSION_LOG, and create
a local Git checkpoint commit. Never commit keys, local .env files, model files,
environments, or transient reports. Do not push without user instruction.

If interrupted, preserve changes and record the exact unfinished action. End
each session with work/tests/next action matching HANDOFF. A completed Phase 1
does not authorize Phase 2; await explicit instruction.
