PROJECT: AgentGate
CURRENT PHASE: Phase 1
LAST VERIFIED MILESTONE: Agent/adapter/structured answer runtime verified; 105 deterministic tests passed
CURRENT TASK: Finish single-request CLI and edge-case tests, verify build/install, finalize documentation
IMPLEMENTED FILES: Scaffold, config/schemas/exceptions, fixtures loader, case state, four tools/registry, adapter, agent, answer rendering, telemetry, synthetic data, baseline prompt and deterministic tests
LATEST TEST COMMAND: uv run --locked python -m pytest -q
LATEST TEST RESULT: 105 passed; no warnings; includes local HTTP stub (not a live LLM)
KNOWN FAILURES: No known code failures; implementation is incomplete
UNVERIFIED ASSUMPTIONS: LLM/Ollama and hardware inference are not tested or required in Phase 1
IMPORTANT DECISIONS: Phase 1 only; workspace itself is project root; src layout; Pydantic plus standard library runtime
NEXT EXACT ACTION: Add minimal single-request CLI without evaluate/gate functionality; test configuration failures and trace persistence; update README/ARCHITECTURE; build/install wheel
FILES TO INSPECT NEXT: src/agentgate/agent.py, src/agentgate/llm_client.py, src/agentgate/answers.py, README.md
REQUIRED COMMANDS: uv run --locked python -m pytest -q; git status --short --branch
