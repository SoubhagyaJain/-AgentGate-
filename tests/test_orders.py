import pytest

from agentgate.exceptions import ToolDenied
from agentgate.schemas import Session
from agentgate.tools import CaseState
from agentgate.tools.orders import get_order


def test_owned_order(state):
    view = get_order(state, "1042")
    assert view.order.customer_id == "alice"
    assert str(view.paid_amount) == "104.00"
    assert view.account_verified


def test_foreign_and_missing_order_identical(state):
    errors = []
    for order_id in ("1050", "nonexistent"):
        with pytest.raises(ToolDenied) as raised:
            get_order(state, order_id)
        errors.append((raised.value.code, raised.value.message))
    assert errors[0] == errors[1] == ("access_denied", "Order unavailable for this session.")


def test_unverified_identity_even_for_owned_order(fixtures):
    state = CaseState(Session(customer_id="alice", identity_verified=False), *fixtures)
    with pytest.raises(ToolDenied, match="unavailable"):
        get_order(state, "1042")
