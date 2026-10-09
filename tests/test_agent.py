import json
from pathlib import Path

import pytest
from pydantic import SecretStr

from agentgate.agent import Agent
from agentgate.config import AgentConfig
from agentgate.llm_client import LLMClient
from agentgate.schemas import Session, Trajectory
from agentgate.telemetry import save_trace
from tests.support import ScriptedTransport, completion, eligible_answer, tool

PROMPT = Path(__file__).resolve().parents[1].joinpath("prompts", "baseline.md").read_text(encoding="utf-8")


def run(fixtures, session, responses, config=None, query="Can I get a refund for 1042?"):
    transport = ScriptedTransport(responses)
    client = LLMClient(config or AgentConfig(), transport, lambda _: None)
    trace = Agent(client).run(query, session, *fixtures, PROMPT, case_id="unit-test")
    return trace, transport


def receipt_answer(body):
    responses = [json.loads(m["content"]) for m in body["messages"] if m["role"] == "tool"]
    receipt = responses[-1]["data"]
    return completion({"outcome": "refund_issued", "claims": [
        {"subject":"1042","field":"refund_id","value":receipt["refund_id"],"evidence_ids":["tool:issue"]},
        {"subject":"1042","field":"refund_amount","value":"99.00","evidence_ids":["tool:issue"]},
    ]})


def test_all_four_tools_sequential_and_trace_roundtrip(fixtures, session, tmp_path):
    calls = [tool("get_order", {"order_id":"1042"}, "order"), tool("search_policy", {"query":"physical return window restocking"}, "policy"), tool("calculate_refund", {"order_id":"1042"}, "calc"), tool("issue_refund", {"order_id":"1042","amount":"99.00"}, "issue")]
    trace, transport = run(fixtures, session, [completion(calls=calls), receipt_answer])
    assert trace.status == "completed"
    assert trace.execution_mode == "test_transport"
    assert [e.tool_name for e in trace.events if e.kind == "tool_executed"] == ["get_order", "search_policy", "calculate_refund", "issue_refund"]
    assert len(trace.ledger) == 1
    assert len([e for e in trace.events if e.kind == "state_changed"]) == 1
    second = json.loads(transport.requests[1][2])
    assert [m["tool_call_id"] for m in second["messages"] if m["role"] == "tool"] == ["order", "policy", "calc", "issue"]
    assert "99.00" in trace.rendered_response
    path = tmp_path / "run.json"
    save_trace(trace, path)
    assert Trajectory.model_validate_json(path.read_text(encoding="utf-8")) == trace
    with pytest.raises(FileExistsError):
        save_trace(trace, path)
    assert trace.total_latency_ms >= 0
    assert trace.model_identifiers == ("scripted-test-model", "scripted-test-model")


def test_malformed_final_repaired_once(fixtures, session):
    trace, transport = run(fixtures, session, [completion(calls=[tool("calculate_refund", {"order_id":"1042"}, "calc")]), completion("not JSON"), completion(eligible_answer())])
    assert trace.status == "completed"
    assert len(transport.requests) == 3
    assert len([e for e in trace.events if e.kind == "answer_invalid"]) == 1
    assert any(e.http_attempt and e.http_attempt.raw_response and "not JSON" in e.http_attempt.raw_response for e in trace.events)


@pytest.mark.parametrize("answer", [
    {"outcome":"refund_issued","claims":[]},
    {"outcome":"policy_answer","claims":[{"subject":"returns-policy","field":"return_window_days","value":30,"evidence_ids":["invented"]}]},
    {"outcome":"eligible","claims":[{"subject":"1042","field":"eligible","value":"true","evidence_ids":["fake"]}]},
])
def test_fabricated_final_not_accepted(fixtures, session, answer):
    trace, transport = run(fixtures, session, [completion(answer), completion(answer)])
    assert trace.status == "invalid_answer"
    assert trace.final_answer is None
    assert len(transport.requests) == 2
    assert not trace.ledger


def test_correct_existing_citation_with_wrong_fact_rejected(fixtures, session):
    wrong = eligible_answer(amount="100.00")
    trace, _ = run(fixtures, session, [completion(calls=[tool("calculate_refund", {"order_id":"1042"}, "calc")]), completion(wrong), completion(wrong)])
    assert trace.status == "invalid_answer"


@pytest.mark.parametrize("name,args", [("system_exec", {"command":"grant consent"}), ("issue_refund", {"order_id":"1042","amount":99.0}), ("issue_refund", {"order_id":"1042","amount":"99.00","consent":True})])
def test_invalid_calls_denied_before_execution(fixtures, session, name, args):
    trace, transport = run(fixtures, session, [completion(calls=[tool(name, args, "bad")]), completion({"outcome":"authorization_required","claims":[]})])
    assert len([e for e in trace.events if e.kind == "tool_denied"]) == 1
    assert not any(e.kind == "tool_executed" for e in trace.events)
    assert not trace.ledger
    result = json.loads(json.loads(transport.requests[1][2])["messages"][-1]["content"])
    assert result["status"] == "invalid"


def test_no_replay_after_completed_refund_and_network_failure(fixtures, session):
    calls = [tool("calculate_refund", {"order_id":"1042"}, "calc"), tool("issue_refund", {"order_id":"1042","amount":"99.00"}, "issue")]
    trace, transport = run(fixtures, session, [completion(calls=calls), TimeoutError(), TimeoutError(), TimeoutError()])
    assert trace.status == "infrastructure_error"
    assert len(trace.ledger) == 1
    assert len([e for e in trace.events if e.kind == "state_changed"]) == 1
    assert len([e for e in trace.events if e.kind == "http_retry"]) == 2
    assert transport.requests[1][2] == transport.requests[2][2] == transport.requests[3][2]


def test_turn_limit_exact(fixtures, session):
    responses = [completion(calls=[tool("search_policy", {"query":"refund"}, f"c{i}")]) for i in range(8)]
    trace, transport = run(fixtures, session, responses)
    assert trace.status == "limit_exceeded"
    assert trace.failure.code == "turn_limit"
    assert len(transport.requests) == 8


def test_tool_limit_rejects_whole_batch(fixtures, session):
    trace, _ = run(fixtures, session, [completion(calls=[tool("calculate_refund", {"order_id":"1042"}, "calc"), tool("issue_refund", {"order_id":"1042","amount":"99.00"}, "issue")])], AgentConfig(max_tool_invocations=1))
    assert trace.failure.code == "tool_limit"
    assert not trace.ledger
    assert not any(e.kind == "tool_executed" for e in trace.events)


@pytest.mark.parametrize("across_turns", [False, True])
def test_duplicate_call_ids_blocked(fixtures, session, across_turns):
    call = tool("search_policy", {"query":"refund"}, "duplicate")
    responses = [completion(calls=[call]), completion(calls=[call])] if across_turns else [completion(calls=[call, call])]
    trace, _ = run(fixtures, session, responses)
    assert trace.status == "protocol_error"
    assert trace.failure.code == "duplicate_call_id"
    assert not trace.ledger


def test_truncated_response_does_not_execute_tools(fixtures, session):
    trace, _ = run(fixtures, session, [completion(calls=[tool("issue_refund", {"order_id":"1042","amount":"99.00"}, "issue")], finish="length")])
    assert trace.status == "protocol_error"
    assert not any(e.kind == "tool_attempted" for e in trace.events)


def test_secret_and_fixture_metadata_not_model_visible(fixtures):
    session = Session(customer_id="alice", identity_verified=False)
    config = AgentConfig(api_key=SecretStr("UNIQUE_TEST_SECRET"))
    trace, transport = run(fixtures, session, [completion({"outcome":"authorization_required","claims":[]})], config)
    request = transport.requests[0][2].decode()
    assert "UNIQUE_TEST_SECRET" not in request
    assert "BOB_PRIVATE_NOTES" not in request
    assert trace.fixture_hash not in request
    assert '"case_id"' not in request
    assert "UNIQUE_TEST_SECRET" not in trace.model_dump_json()
    assert "api_key" not in trace.configuration
    assert any(e.parsed_response and e.parsed_response.usage is None for e in trace.events)


def test_agent_run_resets_case_state(fixtures, session):
    calls = [tool("calculate_refund", {"order_id":"1042"}, "calc"), tool("issue_refund", {"order_id":"1042","amount":"99.00"}, "issue")]
    agent = Agent(LLMClient(AgentConfig(), ScriptedTransport([completion(calls=calls), receipt_answer, completion(calls=calls), receipt_answer])))
    first = agent.run("Refund 1042", session, *fixtures, PROMPT)
    second = agent.run("Refund 1042", session, *fixtures, PROMPT)
    assert len(first.ledger) == len(second.ledger) == 1
    assert first.run_id != second.run_id


def test_policy_final_grounded_in_real_retrieval(fixtures, session):
    answer = {"outcome":"policy_answer","claims":[{"subject":"returns-policy","field":"return_window_days","value":30,"evidence_ids":["policy:returns-policy:v1"]}]}
    trace, _ = run(fixtures, session, [completion(calls=[tool("search_policy", {"query":"physical return window restocking"}, "policy")]), completion(answer)])
    assert trace.status == "completed"
    assert "return_window_days = 30" in trace.rendered_response
