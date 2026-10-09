from datetime import date
from decimal import Decimal

import pytest
from pydantic import SecretStr, ValidationError

from agentgate.config import AgentConfig
from agentgate.exceptions import parse_json
from agentgate.schemas import (
    AgentMessage, Claim, FinalAnswer, IssueArguments, Order, Session, ToolResponse,
)


@pytest.mark.parametrize("amount", [1, 1.0, True, "1", "1.000", "-1.00", "NaN", Decimal("Infinity"), Decimal("1.001")])
def test_money_rejects_ambiguous_values(amount):
    with pytest.raises(ValidationError):
        IssueArguments(order_id="1042", amount=amount)


def test_money_accepts_exact_cents_and_extra_keys_rejected():
    assert IssueArguments(order_id="1042", amount="12.30").amount == Decimal("12.30")
    with pytest.raises(ValidationError):
        IssueArguments(order_id="1042", amount="12.30", consent=True)


def test_session_frozen_and_not_coerced():
    session = Session(customer_id="alice", identity_verified=True)
    with pytest.raises(ValidationError):
        session.identity_verified = False
    with pytest.raises(ValidationError):
        Session(customer_id="alice", identity_verified="true")


@pytest.mark.parametrize("field,value", [("eligible", "true"), ("return_window_days", True), ("refund_amount", 10), ("refund_status", "pending"), ("delivery_date", "tomorrow")])
def test_fact_types(field, value):
    with pytest.raises(ValidationError):
        Claim(subject="1042", field=field, value=value, evidence_ids=("e1",))


def test_final_answer_json_and_role_contracts():
    answer = FinalAnswer.model_validate_json('{"outcome":"eligible","claims":[{"subject":"1042","field":"refund_amount","value":"10.00","evidence_ids":["e1"]}]}')
    assert answer.claims[0].value == "10.00"
    with pytest.raises(ValidationError):
        AgentMessage(role="tool", content="result")
    with pytest.raises(ValidationError):
        ToolResponse(status="ok")


def test_order_consistency():
    with pytest.raises(ValidationError):
        Order(order_id="1", customer_id="alice", purchase_date=date(2026, 10, 1), delivery_status="delivered", item_price="1.00", discount="2.00", tax_paid="0.00", shipping="0.00")


def test_configuration_env_and_secret_exclusion():
    config = AgentConfig.from_env({"AGENTGATE_BASE_URL": "https://example.test/v1", "AGENTGATE_API_KEY": "private-key", "AGENTGATE_MAX_TURNS": "4"})
    assert config.max_turns == 4
    assert "private-key" not in config.model_dump_json()
    assert "private-key" not in repr(config)
    with pytest.raises(ValueError, match="AGENTGATE_MAX_TURNS"):
        AgentConfig.from_env({"AGENTGATE_MAX_TURNS": "eight"})


@pytest.mark.parametrize("url", ["http://example.test/v1", "https://user:pass@example.test/v1", "https://example.test/v1?key=a", "file:///v1", "https://example.test/wrong"])
def test_configuration_rejects_unsafe_endpoints(url):
    with pytest.raises(ValidationError):
        AgentConfig(base_url=url, api_key=SecretStr("secret"))


@pytest.mark.parametrize("values", [{"max_turns": 9}, {"max_tool_invocations": 13}, {"timeout": 0.0}, {"temperature": float("nan")}])
def test_execution_caps(values):
    with pytest.raises(ValidationError):
        AgentConfig(**values)


@pytest.mark.parametrize("raw", ['{"amount":"1.00","amount":"2.00"}', '{"a":NaN}', '{"a":Infinity}'])
def test_duplicate_keys_and_nonfinite_json(raw):
    with pytest.raises(ValueError):
        parse_json(raw)
