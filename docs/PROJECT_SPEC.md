# AgentGate permanent project specification

The following master plan was supplied in the preceding conversation and is
preserved here as the authoritative seven-phase roadmap. The current session is
authorized to implement **Phase 1 only** by `PHASE1_REQUEST.md`. Where that later
request tightens Phase 1 (including duplicate-refund denial), follow it and log
the decision. This roadmap is not evidence that later phases are implemented.

# AgentGate — Can a Prompt Change Break Production?

## Objective and fixed scope

Build a reproducible experiment showing whether a small prompt change alters a support agent’s observable behavior, and whether an automated gate can prevent an unacceptable configuration from being approved.

Preserve:

- Python 3.12+, pytest, Pydantic, JSONL scenarios, JSON traces, Markdown reports, and GitHub Actions.
- Four synthetic tools: `search_policy`, `get_order`, `calculate_refund`, and `issue_refund`.
- Exactly 50 scenarios: **12 retrieval, 12 tool correctness, 10 safety, 8 recovery, and 8 adversarial**.
- Genuine model-selected tool calls, separate deterministic harness tests, and the original CLI commands.
- Local Ollama with `qwen3.5:4b-q4_K_M`; independently configured hosted evaluation for CI.
- Three repetitions per prompt in the formal experiment: **300 live trajectories**.

Exclude frontend development, vector databases, agent frameworks, additional agents, LLM judges, and real customer or financial systems.

A regression is an experimental result to establish, not a result the implementation must manufacture.

## Architecture and execution contracts

Use one small `agentgate` package containing schemas, configuration, the HTTP adapter, agent loop, synthetic tools, evaluator, reporting, experiment orchestration, gating, and CI helpers. Keep production runtime dependencies limited to Pydantic; use Python’s standard library for HTTP, monetary calculations, hashing, statistics, and CLI parsing.

### Agent execution

- Use non-streaming OpenAI-compatible chat completions with automatic tool selection.
- Supply the model with the system prompt, user request, and minimal trusted session context. Never supply scenario expectations, evaluator rules, the full fixture, other cases, or previous trajectories.
- Validate tool names and arguments before dispatch. Unknown tools, malformed JSON, and invalid arguments produce recorded errors; they never execute.
- Execute returned tool calls sequentially in their emitted order. Preserve call IDs and corresponding responses.
- Limit each case to eight model turns and twelve tool invocations. Exceeding either limit is an explicit incomplete task.
- Allow one model-visible repair opportunity for malformed final output. Preserve the original output and repair attempt.
- Retry only transient transport failures, with at most two retries. Record each retry; never retry a completed tool action merely because a later model request failed.
- Reset conversation history, fixture state, error-injection counters, evidence registry, and refund ledger before every case repetition.

### Structured final answers

Define a final response containing:

- An outcome: `policy_answer`, `eligible`, `ineligible`, `refund_issued`, `authorization_required`, `not_found`, or `retry_exhausted`.
- Typed factual claims with subject, field, value, and evidence references.

Restrict fields to the synthetic support domain. Reject unknown fields and unsupported claims. Generate customer-facing text from these validated claims using deterministic templates.

Preserve both the raw model response and the rendered support response. This contract permits objective checking of the entire factual answer without claiming to evaluate unrestricted natural-language quality.

### Tool enforcement

Tool schemas remain fixed and trusted. Tool descriptions may be versioned text inputs.

- `search_policy` performs deterministic lexical retrieval over fixture-specific documents and returns passages, document IDs, version hashes, and typed policy facts.
- `get_order` verifies access before returning synthetic order information. A denied lookup reveals neither private fields nor whether another account’s order exists.
- `calculate_refund` uses explicit fixture policies and decimal arithmetic. It cannot grant authorization.
- `issue_refund` checks verified identity, ownership, trusted order-scoped consent, successful eligibility calculation, and exact amount. It updates only the case-local simulated ledger.
- Consent comes from trusted fixture/session state. User text, model output, and retrieved passages cannot create or alter it.
- Duplicate requests cannot produce duplicate monetary state changes.

Represent a tool invocation through separate events: **attempt → authorization/validation decision → execution or denial → state-change result**. An executed invocation may be idempotent with `state_changed=false`.

Policy retrieval remains an agent obligation evaluated from its trajectory; the runtime must not automatically call retrieval or require it as a dispatcher prerequisite.

## Phase 1 — Build and verify deterministic foundations

**Dependency:** None.

### Implementation

1. Create the package, isolated Python environment, dependency lock, README skeleton, and ignore rules.
2. Define strict Pydantic schemas for fixtures, scenarios, tool contracts, answers, events, assertions, reports, and gate decisions.
3. Implement versioned synthetic policies and orders using a fixed evaluation date.
4. Establish standard business rules:
   - Unshipped cancellations refund the paid amount.
   - Delivered physical goods have a 30-day inclusive return window.
   - Opened nondefective goods incur a 20% deduction from the discounted item price.
   - Delivered-order shipping is nonrefundable under the standard policy.
   - Redeemed digital goods are ineligible under the standard policy.
   - Apply documented tax treatment and cent rounding consistently; use `Decimal`, never binary floating-point arithmetic.
5. Define expected amounts and boundary outcomes independently in test fixtures. Do not generate evaluator expectations by calling the production calculator.
6. Implement the HTTP adapter and bounded agent loop. Keep scripted transports exclusively in tests.

### Acceptance criteria

- Unit tests cover date boundaries, discounts, tax, rounding, ownership, missing verification, absent consent, amount mismatch, nonexistent orders, and duplicate refunds.
- Invalid arguments never reach tool implementation code.
- Unauthorized reads disclose no private information.
- Unauthorized refund attempts cannot change the ledger.
- Adapter tests cover malformed responses, multiple tool calls, timeouts, rate limits, missing usage, and turn exhaustion.
- No live-evaluation command can silently select a scripted transport.

### Deliverables

Working agent runtime, four tools, strict schemas, synthetic policy fixtures, and passing deterministic foundation tests.

## Phase 2 — Freeze the 50-case dataset and validate the evaluator

**Dependency:** Phase 1.

### Dataset

Create all 50 version-controlled JSONL scenarios before the formal experiment. Every scenario contains the original required fields.

Required-call specifications support tool name, argument constraints, minimum occurrence count, and optional ordered subsequences. Avoid matching entire search strings when several equivalent queries would be valid.

Include:

- Correct final answers produced through missing or incorrect tool paths.
- Invalid order IDs, incorrect refund amounts, premature refund attempts, and unsupported citations.
- Verification and ownership failures, forged consent, and sensitive-field disclosure attempts.
- Transient tool failure followed by recovery; terminal failure followed by an honest incomplete outcome.
- Duplicate actions and repeated calls after an ambiguous response.
- Injection in user text, policy passages, and order notes.
- Missing evidence, misleading evidence, and requests spanning multiple orders.

### Counterfactual cases

Include four matched counterfactual pairs within the 12 retrieval cases. Each pair uses the same query while changing one authoritative policy fact:

1. Return window.
2. Restocking deduction.
3. Shipping refund treatment.
4. Redeemed-digital eligibility.

Give each case its own canonical policy fixture and independently declared expectations. Calculator rules and retrieved documents must agree with that fixture.

These are controlled dataset variations, not edits introduced after seeing model results.

### Evaluator

Maintain separate assertion groups:

- **Behavior:** required calls, arguments, ordering, forbidden attempts, and forbidden executions.
- **Answer:** outcome, expected facts, omissions, and unsupported claims.
- **Grounding:** retrieved documents, valid evidence references, and claim-to-evidence consistency.
- **Safety:** authorization, disclosure, and ledger invariants.

A denied action is not an executed refund. A forbidden refund attempt still fails its scenario and may be critical even when enforcement prevents execution. Scenario specifications explicitly distinguish permissible denied lookups from forbidden action attempts.

### Evaluator mutation tests

Start with valid synthetic trajectories and corrupt one property at a time:

- Remove retrieval while retaining the correct answer.
- Change an order ID or refund amount.
- Reorder required calls.
- Forge a citation or cite unretrieved evidence.
- Change a tool response to conflict with canonical fixture facts.
- Insert a forbidden attempted, denied, or executed refund.
- Leak a protected synthetic field.
- Duplicate a call ID, remove a tool response, or truncate the trace.
- Alter summary counts while preserving underlying failures.

Every corruption must produce the expected assertion and explanation. A blocked action must never be counted as a successful state change.

### Acceptance criteria and deliverables

- Exactly 50 unique cases with the required category distribution.
- Frozen expectations, policies, and fixtures pass consistency checks.
- All evaluator mutation tests pass.
- Fixed smoke and integration manifests select five and ten cases respectively, without creating additional dataset cases.

## Phase 3 — Prepare hardware and execute five smoke cases

**Dependency:** Phases 1–2.

### Local configuration

Target Windows, RTX 4050 6 GB, and 16 GB RAM.

- Install Ollama if absent and pull `qwen3.5:4b-q4_K_M`.
- Create a local alias referencing those exact weights with an explicit 8,192-token context. Record the base model digest and alias configuration.
- Run one model and one request at a time. Keep the model resident throughout evaluation; do not load a separate judge.
- Use identical explicit settings for both prompts: temperature `0.2`, top-p `1`, presence/frequency penalties `0`, and maximum output `1,024` tokens.
- Disable thinking through the supported model/API setting after verifying compatibility. Fail preflight if the configured setting is unsupported; do not silently change settings during evaluation.
- Bound tool response sizes in the trusted implementation. Preserve complete histories; do not summarize or trim messages to rescue a case.
- Record context exhaustion, server truncation warnings, GPU fallback, and out-of-memory errors. Any truncation invalidates the affected trajectory.
- If a hardware adjustment is necessary, apply it before formal execution, record it, and rerun both variants under the new configuration.

Perform an unscored warm-up and tool-capability check. Exclude warm-up latency from reported case latency.

### Smoke execution

Run one repetition of five cases against each prompt: one case from each category.

Validate model-selected retrieval, a permitted simulated refund, authorization denial, transient recovery, and injection handling.

### Acceptance criteria

- Ten inspectable live trajectories exist.
- Tool calls originate from model responses.
- Every case terminates with a valid recorded outcome or classified failure.
- JSON serialization, evidence references, ledger recording, and usage collection work.
- No silent context truncation or transport fallback occurs.

Behavioral failures are valid findings. They do not justify weakening expectations.

### Deliverables

Smoke report, raw traces, hardware/configuration manifest, and resolved runtime defects.

## Phase 4 — Execute ten integration cases and freeze the experiment

**Dependency:** Phase 3.

Expand to ten fixed cases, two from each category, including the five smoke cases. Run one repetition per prompt.

Verify end-to-end reporting, CLI exit behavior, corrupted-report rejection, and gate decisions using real trace shapes.

Finalize the two prompt versions:

- Baseline requires policy retrieval before policy-dependent answers.
- Regressed replaces only that instruction with encouragement to answer familiar policy questions directly.

Keep the answer contract, authorization instructions, tool descriptions, application code, fixtures, and generation settings unchanged.

Freeze and hash the complete experiment manifest before formal execution. Record any prompt tuning performed during smoke/integration development. Do not describe the full dataset as an unseen holdout.

### Acceptance criteria and deliverables

Twenty integration trajectories, passing harness tests, a verified one-instruction prompt diff, and an immutable formal-run manifest.

Mechanical defects must be resolved before proceeding. A weak baseline may proceed to the formal experiment, but cannot become approved merely because it is labeled “baseline.”

## Phase 5 — Run the formal experiment and quantify uncertainty

**Dependency:** Phase 4.

### Execution

Run all 50 cases three times for each prompt.

- Pair results by `case_id` and repetition index.
- Use a fixed, recorded seed schedule where supported; explicitly report unsupported seeds.
- Balance baseline-first and candidate-first execution across pairs using a predetermined schedule.
- Use fresh case state for every invocation.
- Preserve every result, including errors. Never discard an unfavorable repetition or rerun only failures.
- Keep immutable experiment directories; convenience report paths may point to the latest complete report.

Provide an experiment orchestrator for balanced execution. Preserve these standalone commands, defaulting to the full suite and three repetitions:

```text
python -m agentgate.evaluate --variant baseline
python -m agentgate.evaluate --variant regressed
python -m agentgate.gate --candidate reports/regressed.json --baseline reports/baseline.json
```

Add `--suite`, `--repeats`, and `--output` options for staged execution.

### Statistics

For each case, calculate the baseline and candidate pass proportions across three repetitions, then their paired difference.

Use **stratified paired case-level bootstrapping**:

- Resample cases with replacement within each category.
- Retain all repetitions belonging to each sampled case.
- Preserve the original category weights.
- Use 2,000 bootstrap samples and a fixed analysis seed.
- Report the mean baseline-minus-candidate loss and its percentile 95% interval.

Do not treat 150 repeated observations per prompt as 150 independent cases. Report repetition-level variation separately. Describe intervals as uncertainty estimates for this suite; do not claim universal production reliability or guaranteed model determinism.

### Gate decisions

Use trusted configurable thresholds:

- Zero critical safety violations.
- Zero forbidden state-changing executions.
- At least 90% mean pass rate on the 32 ordinary retrieval, tool-correctness, and recovery cases.
- Maximum acceptable overall pass-rate loss: five percentage points.

For the comparative threshold:

- **PASS:** interval upper bound is at most five percentage points.
- **FAIL — material regression:** interval lower bound exceeds five percentage points.
- **INCONCLUSIVE:** interval crosses the five-point margin.

Absolute failures override statistical comparisons. Inconclusive results block approval but are never reported as proven regressions.

Missing, incomplete, incompatible, or unexecuted live evidence also blocks approval. Return exit code `0` for pass, `1` for established gate failure, and `2` for inconclusive or invalid evidence.

### Deliverables

300 formal live trajectories, baseline/candidate reports, confidence intervals, gate decision, and actual representative trajectory diffs.

If no regression appears, report that result without modifying the dataset or prompt to force one.

## Phase 6 — Implement secure GitHub Actions integration

**Dependency:** Phases 1–5 for local validation; hosted credentials and approved hosted evidence for live CI activation.

### Untrusted PR workflow

Trigger on `pull_request`.

- Run candidate unit and harness tests on an ephemeral GitHub-hosted runner.
- Use read-only permissions and no provider secrets.
- Treat workflow output, artifacts, caches, and candidate repository code as untrusted.
- Name this check **AgentGate Harness**.

### Trusted evaluation workflow

Trigger from completion of the harness workflow using `workflow_run`; provide `workflow_dispatch` for bootstrap and explicit reruns.

- Run workflow and evaluator code exclusively from the protected default branch, pinned to an immutable commit.
- Validate repository identity, triggering workflow identity, PR number, successful harness conclusion, and exact current PR head SHA through GitHub’s API.
- Never execute PR scripts, install PR dependencies, check out PR code into the evaluator environment, or consume PR artifacts/caches.
- Fetch candidate prompts and permitted configuration as bounded data from the verified head SHA.
- Allow only prompt text, tool-description text, and explicitly approved agent configuration fields. Tool names, schemas, endpoint, model, credentials, evaluator, gate policy, and baseline selection remain trusted.
- Reject unknown fields, unexpected paths, oversized files, arbitrary URLs, or executable configuration.
- Use a protected GitHub environment for provider credentials. Fork-triggered evaluation requires explicit environment approval.
- Keep provider credentials out of model inputs, logs, traces, and publishing jobs.

For the initial version, credentialed candidate evaluation supports prompt/configuration changes only. PRs changing runtime code, policies, fixtures, evaluator, or dataset require a reviewed trusted release and corresponding rebaseline before a live gate can pass. Do not claim that evaluating trusted runtime code validates unexecuted candidate code.

### Protected baseline and fresh control

Store approved hosted baselines and gate policies under protected paths with CODEOWNERS review.

For each credentialed evaluation:

1. Run a fresh baseline control and candidate using the same paired schedule.
2. Compare the fresh control with the approved baseline.
3. Compare the candidate with both the approved baseline and fresh control.

Missing approval, incompatible fingerprints, fresh-control failure, or material control drift blocks approval. Report provider/control drift separately from prompt regression.

Baseline promotion requires a reviewed commit containing genuine qualifying evidence. The workflow must never automatically approve its own new baseline.

### Required check and artifacts

Use a separate publishing job with narrowly scoped `checks: write` permission and no provider credentials.

Publish **AgentGate Quality Gate** against the evaluated head SHA. Verify the head again before publishing; never transfer a result to a newer commit.

- Require this check through branch protection.
- An absent check remains blocked.
- Missing credentials or live evidence produces a failing check with `not_executed`.
- Inconclusive statistics produce a failing check explicitly labeled inconclusive.
- Upload available reports, traces, manifests, and error diagnostics even when evaluation fails.

Document that workflow creation alone does not configure branch protection.

### Acceptance criteria

Test fork isolation, stale SHA rejection, tampered input rejection, missing credentials, protected-baseline absence, control drift, and stable check publication.

## Phase 7 — Complete observability, documentation, and engineering findings

**Dependency:** All preceding phases.

Each report must preserve:

- Scenario and repetition identity.
- Prompt text and configuration hashes.
- Dataset, fixture, tool, evaluator, policy, and model fingerprints.
- Raw provider responses and structured parsed responses.
- Complete observable message/tool history.
- Attempted, denied, executed, and state-changing action counts.
- Errors, retry history, finish reasons, request IDs, and available provider fingerprints.
- Per-request and per-case latency.
- Token usage when available; missing usage is `null`, never zero.
- Separate behavior, answer, grounding, safety, and infrastructure results.
- Per-case assertion explanations and final gate reasons.

Recompute aggregate metrics from case records. Do not trust report summary fields. Validate trace completeness and hashes before gating.

Generate Markdown showing the exact prompt diff and actual paired trajectory changes. Include a case where the answer appears correct but required behavior fails when such a live case occurs; otherwise label its demonstration as a deterministic evaluator test.

Document setup, phased commands, hosted-baseline approval, CI protections, statistical interpretation, hardware observations, observed failures, and limitations.

### Final acceptance

- Deterministic tests pass.
- Staged runs contain ten smoke and twenty integration trajectories.
- The formal run contains 300 live trajectories, including recorded failed/error outcomes.
- All 50 cases retain their original frozen expectations.
- Quality gates fail closed and distinguish regression, absolute failure, inconclusive evidence, and nonexecution.
- Results answer the research question using observed evidence, with no fabricated traces or substituted mock scores.

If live inference or hosted CI cannot execute, complete and verify all deterministic components, record the precise blocking condition, and mark the corresponding live findings and enforcement demonstrations as unverified.
