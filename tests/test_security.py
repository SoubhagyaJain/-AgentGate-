import json

import pytest

from agentgate.schemas import FunctionCall, Session, ToolCall
from agentgate.telemetry import TraceRecorder
from agentgate.tools import CaseState, ToolRegistry


def call(name, arguments, call_id="c1"):
    return ToolCall(id=call_id, function=FunctionCall(name=name, arguments=json.dumps(arguments)))


@pytest.mark.parametrize("name,args,code", [
    ("grant_consent", {"order_id": "1042"}, "unknown_tool"),
    ("issue_refund", {"order_id": "1042", "amount": "99.00", "consent": True}, "invalid_arguments"),
    ("issue_refund", {"order_id": "1042", "amount": 99.0}, "invalid_arguments"),
    ("get_order", {"order_id": "1050", "customer_id": "bob"}, "invalid_arguments"),
    ("get_order", {"order_id": "../../secret"}, "invalid_arguments"),
])
def test_untrusted_arguments_cannot_grant_privileges(registry, name, args, code):
    response = registry.dispatch(call(name, args))
    assert response.error.code == code
    assert not registry.state.ledger
    assert [e.kind for e in registry.trace.events] == ["tool_attempted", "tool_denied"]


def test_foreign_missing_responses_do_not_disclose_existence(registry):
    first = registry.dispatch(call("get_order", {"order_id": "1050"}, "c1"))
    second = registry.dispatch(call("get_order", {"order_id": "missing"}, "c2"))
    assert first == second
    assert "bob" not in first.model_dump_json()
    assert "BOB_PRIVATE" not in first.model_dump_json()


def test_denied_attempt_not_execution_or_state_change(fixtures):
    registry = ToolRegistry(CaseState(Session(customer_id="alice", identity_verified=True), *fixtures), TraceRecorder())
    registry.dispatch(call("calculate_refund", {"order_id": "1042"}, "calc"))
    response = registry.dispatch(call("issue_refund", {"order_id": "1042", "amount": "99.00"}, "issue"))
    assert response.status == "denied"
    assert [e.kind for e in registry.trace.events if e.call_id == "issue"] == ["tool_attempted", "tool_denied"]
    assert not registry.state.ledger


def test_success_records_distinct_state_change(registry):
    registry.dispatch(call("calculate_refund", {"order_id": "1042"}, "calc"))
    registry.dispatch(call("issue_refund", {"order_id": "1042", "amount": "99.00"}, "issue"))
    assert [e.kind for e in registry.trace.events if e.call_id == "issue"] == ["tool_attempted", "tool_executed", "state_changed"]


def test_duplicate_call_id_never_executes(registry):
    first = call("calculate_refund", {"order_id": "1042"})
    registry.dispatch(first)
    response = registry.dispatch(first)
    assert response.error.code == "duplicate_call_id"
    assert len([e for e in registry.trace.events if e.kind == "tool_executed"]) == 1


def test_duplicate_argument_keys_rejected(registry):
    response = registry.dispatch(ToolCall(id="c1", function=FunctionCall(name="get_order", arguments='{"order_id":"1042","order_id":"1050"}')))
    assert response.error.code == "invalid_arguments"


def test_tool_definitions_fixed_and_money_text(registry):
    definitions = registry.definitions()
    assert {d.function.name for d in definitions} == {"search_policy", "get_order", "calculate_refund", "issue_refund"}
    issue = next(d for d in definitions if d.function.name == "issue_refund")
    assert issue.function.parameters["properties"]["amount"]["type"] == "string"
    assert issue.function.parameters["additionalProperties"] is False
