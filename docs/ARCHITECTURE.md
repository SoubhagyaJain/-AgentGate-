# Phase 1 architecture

Trusted configuration/session/fixtures -> bounded agent -> HTTP adapter -> model.
Model calls -> strict registry -> synthetic tools -> evidence/state -> model.
All observable steps -> typed trajectory -> JSON artifact.

Model text cannot alter sessions, consent, tools, business policies or ledgers.
Later evaluators consume trajectories; Phase 1 contains no evaluator or dataset.

Runtime responsibilities and verified interfaces will be filled in as each
implementation milestone is completed; consult PROGRESS and HANDOFF for status.
