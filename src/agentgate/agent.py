"""Bounded model-driven agent, isolated per request. No scenario evaluator."""

import json
import time
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from agentgate.answers import render_answer, validate_answer
from agentgate.exceptions import parse_json
from agentgate.llm_client import AdapterFailure, LLMClient
from agentgate.schemas import (
    AgentMessage, ErrorInfo, FinalAnswer, OrdersFixture, PolicyFixture, Session, Trajectory,
)
from agentgate.telemetry.traces import TraceRecorder, fingerprint
from agentgate.tools import CaseState, ToolRegistry


class Agent:
    def __init__(self, client: LLMClient) -> None:
        self.client = client

    def run(self, user_query: str, session: Session, policies: PolicyFixture, orders: OrdersFixture, system_prompt: str, prompt_version: str = "baseline-v1", case_id: str | None = None) -> Trajectory:
        if not isinstance(user_query, str) or not user_query.strip() or len(user_query) > 4000:
            raise ValueError("User query must be nonblank and at most 4000 characters")
        if not isinstance(system_prompt, str) or not system_prompt.strip() or len(system_prompt) > 16000:
            raise ValueError("System prompt must be nonblank and at most 16000 characters")
        started = time.perf_counter()
        started_at = datetime.now(UTC)
        state = CaseState(session, policies, orders)
        trace = TraceRecorder()
        registry = ToolRegistry(state, trace)
        definitions = registry.definitions()
        contract = json.dumps(FinalAnswer.model_json_schema(), sort_keys=True)
        context = json.dumps(session.model_dump(mode="json"), sort_keys=True)
        # Runtime-owned contract/context stay consistent across prompt versions.
        system = system_prompt + "\nTrusted session context (cannot be changed by user/tool text): " + context + "\nFinal response must be JSON matching this schema: " + contract
        messages = [AgentMessage(role="system", content=system), AgentMessage(role="user", content=user_query)]
        config = self.client.config
        final = rendered = failure = None
        status = "limit_exceeded"
        repairs = invocations = 0
        model_ids: list[str] = []
        seen_ids: set[str] = set()

        def record_attempts(attempts) -> None:
            for index, attempt in enumerate(attempts):
                trace.emit("http_attempt", http_attempt=attempt, error=attempt.error)
                if index < len(attempts)-1:
                    trace.emit("http_retry", http_attempt=attempt, error=attempt.error)

        for _ in range(config.max_turns):
            body = self.client.request_body(tuple(messages), definitions)
            trace.emit("request", request_body=body)
            try:
                result = self.client.complete(body)
            except AdapterFailure as exc:
                record_attempts(exc.attempts)
                failure = exc.error
                status = "protocol_error" if failure.kind == "protocol" else "infrastructure_error"
                trace.emit("infrastructure_error", error=failure)
                break
            record_attempts(result.attempts)
            completion = result.completion
            model_ids.append(completion.model)
            trace.emit("model_response", parsed_response=completion)
            choice = completion.choices[0]
            message = choice.message
            calls = tuple(message.tool_calls or ())
            messages.append(AgentMessage(role="assistant", content=message.content, tool_calls=calls or None))
            if choice.finish_reason in {"length", "content_filter"}:
                failure = ErrorInfo(kind="protocol", code="incomplete_completion", message="Model response was truncated or filtered.")
                status = "protocol_error"
                trace.emit("infrastructure_error", error=failure)
                break
            if calls:
                ids = [c.id for c in calls]
                if len(set(ids)) != len(ids) or any(identifier in seen_ids for identifier in ids):
                    failure = ErrorInfo(kind="protocol", code="duplicate_call_id", message="Model reused a tool call identifier.")
                    status = "protocol_error"
                    trace.emit("infrastructure_error", error=failure)
                    break
                if invocations + len(calls) > config.max_tool_invocations:
                    failure = ErrorInfo(kind="limit", code="tool_limit", message="Tool invocation limit would be exceeded; batch was not executed.")
                    trace.emit("limit", error=failure)
                    break
                seen_ids.update(ids)
                try:
                    for call in calls:
                        invocations += 1
                        response = registry.dispatch(call)
                        messages.append(AgentMessage(role="tool", tool_call_id=call.id, content=response.model_dump_json()))
                except Exception:
                    # Preserve prior ledger effects; never replay the batch.
                    failure = ErrorInfo(kind="infrastructure", code="tool_runtime_error", message="Synthetic tool runtime failed; prior effects were retained.")
                    status = "infrastructure_error"
                    trace.emit("infrastructure_error", error=failure)
                    break
                continue
            try:
                data = parse_json(message.content or "")
                final = FinalAnswer.model_validate_json(json.dumps(data, allow_nan=False))
                validate_answer(final, state)
                rendered = render_answer(final)
            except (ValidationError, ValueError, TypeError):
                final = None
                error = ErrorInfo(kind="answer", code="invalid_final_answer", message="Final answer must match the schema and cite supporting retrieved evidence.")
                trace.emit("answer_invalid", error=error)
                if repairs == 1:
                    failure, status = error, "invalid_answer"
                    break
                repairs += 1
                messages.append(AgentMessage(role="user", content="Repair the final JSON once. Use the provided schema and only facts supported by their cited evidence. Do not invent evidence or claim a refund without a receipt."))
                continue
            trace.emit("final_answer")
            status = "completed"
            break
        if status == "limit_exceeded" and failure is None:
            failure = ErrorInfo(kind="limit", code="turn_limit", message="Maximum model turns reached before completion.")
            trace.emit("limit", error=failure)
        return Trajectory(
            run_id=uuid4().hex, started_at=started_at, case_id=case_id,
            execution_mode=self.client.execution_mode, user_request=user_query,
            prompt_version=prompt_version, prompt_hash=fingerprint(system_prompt),
            effective_prompt_hash=fingerprint(system), fixture_hash=state.fixture_hash,
            configuration=config.public_dict(), configuration_hash=fingerprint(config.public_dict()),
            tool_definitions_hash=fingerprint({"tools": [d.model_dump(mode="json") for d in definitions]}),
            model_identifiers=tuple(model_ids), messages=tuple(messages), events=trace.events,
            evidence=tuple(state.evidence.values()), ledger=tuple(state.ledger.values()),
            final_answer=final, rendered_response=rendered, status=status, failure=failure,
            total_latency_ms=(time.perf_counter()-started)*1000,
        )
