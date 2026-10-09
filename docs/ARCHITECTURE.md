# Phase 1 architecture

Trusted configuration/session/fixtures -> bounded agent -> HTTP adapter -> model.
Model calls -> strict registry -> synthetic tools -> evidence/state -> model.
All observable steps -> typed trajectory -> JSON artifact.

Model text cannot alter sessions, consent, tools, business policies or ledgers.
Later evaluators consume trajectories; Phase 1 contains no evaluator or dataset.

## Modules and interfaces

- `config.py`: immutable environment configuration and credential exclusion.
- `schemas.py`: strict domain contracts, provider parsing, typed events/trajectories.
- `fixtures/loader.py`: trusted explicit JSON paths; duplicate-key/fixture validation.
- `tools/state.py`: case-local private orders, calculations, evidence and ledger;
  immutable trusted session/policies and read-only external mappings.
- `tools/policies.py`, `orders.py`, `refunds.py`: actual deterministic synthetic
  operations; authorization enforced in every order-related operation.
- `tools/registry.py`: fixed definitions, strict argument validation, dispatch and
  distinct attempt/denial/execution/state-change telemetry.
- `llm_client.py`: stdlib HTTP transport, redirect refusal, three-attempt cap,
  bounded response parsing, safe errors, raw/parsed response separation.
- `agent.py`: fresh state per run; sequential model-selected calls, shared turn/
  invocation budgets, one final repair, complete observable trajectory return.
- `answers.py`: supports every cited factual claim and outcome binding; deterministic
  display. This is runtime validation, not a scenario evaluator.
- `telemetry/traces.py`: hashes, monotonically sequenced events and immutable JSON persistence.
- `__main__.py`: single operator request or no-network input validation. No evaluate/gate shim.

Public Python usage:

```python
from pathlib import Path
from agentgate.agent import Agent
from agentgate.config import AgentConfig
from agentgate.fixtures import load_fixtures
from agentgate.llm_client import LLMClient
from agentgate.schemas import Session
from agentgate.telemetry import save_trace

policies, orders = load_fixtures(Path("data/fixtures"))
session = Session(customer_id="alice", identity_verified=False)
trace = Agent(LLMClient(AgentConfig.from_env())).run(
    user_query="Can I get a refund for 1042?",
    session=session, policies=policies, orders=orders,
    system_prompt=Path("prompts/baseline.md").read_text(encoding="utf-8"),
    prompt_version="baseline-v1", case_id=None,
)
save_trace(trace, Path("reports") / (trace.run_id + ".json"))
```

This example performs a real request only if deliberately executed against a
configured endpoint; it was not executed as a live test in Phase 1.

## Trust boundaries and later integration

Provider-added metadata is retained in raw response text, while known wire fields
are parsed strictly. Domain schemas forbid extra fields/coercion. Money JSON is
text; no implicit conversion from floats. User/tool text never changes a Session.
Tool-call IDs correlate responses and events and cannot be reused.

Retries replay only encoded model HTTP requests, not local tool dispatch. On
failure the trace includes the surviving ledger and incomplete status. Denied
actions cannot create evidence or state changes. Case ledgers are deliberately
not shared or persisted as a cross-session financial database.

Later evaluation receives `Trajectory`, including raw outputs, messages, events,
evidence and ledger, and independently scores expected behavior and final answer.
`status=completed` only means the runtime accepted a grounded structured response;
it does not mean tool-path correctness, safety or task expectations passed.
No later-phase placeholders/scenarios/scores have been introduced.
