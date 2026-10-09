PROJECT: AgentGate
CURRENT PHASE: Phase 1
LAST VERIFIED MILESTONE: Four synthetic tools and case isolation verified; 68 deterministic tests passed
CURRENT TASK: Implement HTTP adapter, bounded runtime and structured answer validation/rendering
IMPLEMENTED FILES: Scaffold, config/schemas/exceptions, fixtures loader, case state, four tools/registry, telemetry recorder/writer, synthetic data and tests
LATEST TEST COMMAND: uv run --locked python -m pytest -q
LATEST TEST RESULT: 68 passed; no warnings
KNOWN FAILURES: No known code failures; implementation is incomplete
UNVERIFIED ASSUMPTIONS: LLM/Ollama and hardware inference are not tested or required in Phase 1
IMPORTANT DECISIONS: Phase 1 only; workspace itself is project root; src layout; Pydantic plus standard library runtime
NEXT EXACT ACTION: Implement llm_client.py/agent.py/answers.py and test HTTP retries, multi-call order, limits, repair, traces and secret exclusion
FILES TO INSPECT NEXT: src/agentgate/schemas.py, src/agentgate/tools/registry.py, src/agentgate/telemetry/traces.py
REQUIRED COMMANDS: uv run --locked python -m pytest -q; git status --short --branch
