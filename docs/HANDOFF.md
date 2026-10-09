PROJECT: AgentGate
CURRENT PHASE: Phase 1
LAST VERIFIED MILESTONE: Strict schemas/configuration implemented; 31 deterministic tests passed
CURRENT TASK: Implement fixture loader and four synthetic tools with security tests
IMPLEMENTED FILES: AGENTS.md, pyproject.toml, .env.example, .gitignore, README.md, src/agentgate/__init__.py, docs continuity skeletons
LATEST TEST COMMAND: uv run --locked python -m pytest tests/test_schemas.py -q
LATEST TEST RESULT: 31 passed (first run had a OneDrive pytest-cache rename warning; cache plugin disabled and rerun before checkpoint)
KNOWN FAILURES: No known code failures; implementation is incomplete
UNVERIFIED ASSUMPTIONS: LLM/Ollama and hardware inference are not tested or required in Phase 1
IMPORTANT DECISIONS: Phase 1 only; workspace itself is project root; src layout; Pydantic plus standard library runtime
NEXT EXACT ACTION: Implement fixtures/loader.py, tools/state.py, tools/{policies,orders,refunds,registry}.py; test exact tax rules and unauthorized dispatch
FILES TO INSPECT NEXT: src/agentgate/schemas.py, docs/DECISIONS.md, docs/PHASE1_REQUEST.md
REQUIRED COMMANDS: uv run --locked python -m pytest -q; git status --short --branch
