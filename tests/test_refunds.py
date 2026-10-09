from datetime import date
from decimal import Decimal

import pytest

from agentgate.exceptions import ToolDenied
from agentgate.schemas import Order, OrdersFixture, Session
from agentgate.tools import CaseState
from agentgate.tools.refunds import calculate_refund, issue_refund


@pytest.mark.parametrize("order_id,eligible,amount,reason", [
    ("1042", True, "99.00", "within_window"),
    ("1043", True, "79.19", "within_window"),
    ("1044", True, "110.00", "within_window"),
    ("1045", False, "0.00", "window_expired"),
    ("1046", True, "93.00", "unshipped_cancellation"),
    ("1047", False, "0.00", "digital_redeemed"),
    ("1048", True, "43.99", "digital_unredeemed"),
    ("1049", False, "0.00", "in_transit"),
    ("1051", True, "110.00", "within_window"),
])
def test_independent_expected_amounts(state, order_id, eligible, amount, reason):
    result = calculate_refund(state, order_id)
    assert result.eligible is eligible
    assert result.amount == Decimal(amount)
    assert result.reason == reason


def test_discount_deduction_tax_and_rounding(state):
    result = calculate_refund(state, "1043")
    assert result.deduction == Decimal("18.00")
    assert result.tax_refund == Decimal("7.20")


def test_half_cent_rounds_up(fixtures, session):
    order = Order(order_id="tiny", customer_id="alice", purchase_date=date(2026, 10, 1), delivery_date=date(2026, 10, 2), delivery_status="delivered", item_price="0.06", discount="0.00", tax_paid="0.03", shipping="0.00", opened=True)
    result = calculate_refund(CaseState(session, fixtures[0], OrdersFixture(orders=(order,))), "tiny")
    assert result.deduction == Decimal("0.01")
    # 0.03 * (0.05 / 0.06) == 0.025, rounded half up to 0.03.
    assert result.tax_refund == Decimal("0.03")
    assert result.amount == Decimal("0.08")


def test_zero_value_avoids_division_by_zero(fixtures, session):
    order = Order(order_id="free", customer_id="alice", purchase_date=date(2026, 10, 1), delivery_date=date(2026, 10, 2), delivery_status="delivered", item_price="10.00", discount="10.00", tax_paid="0.00", shipping="0.00", opened=True)
    result = calculate_refund(CaseState(session, fixtures[0], OrdersFixture(orders=(order,))), "free")
    assert not result.eligible
    assert result.reason == "nothing_paid"


@pytest.mark.parametrize("amount", [Decimal("0.00"), Decimal("98.99"), Decimal("99.01")])
def test_wrong_amount_does_not_mutate(state, amount):
    calculate_refund(state, "1042")
    with pytest.raises(ToolDenied, match="match"):
        issue_refund(state, "1042", amount)
    assert not state.ledger


def test_calculation_required(state):
    with pytest.raises(ToolDenied, match="Calculate"):
        issue_refund(state, "1042", Decimal("99.00"))
    assert not state.ledger


def test_duplicate_prevention_and_case_isolation(state, fixtures, session):
    calculate_refund(state, "1042")
    receipt = issue_refund(state, "1042", Decimal("99.00"))
    with pytest.raises(ToolDenied, match="already issued"):
        issue_refund(state, "1042", Decimal("99.00"))
    assert tuple(state.ledger.values()) == (receipt,)
    assert not calculate_refund(state, "1042").eligible
    assert not CaseState(session, *fixtures).ledger


def test_missing_consent_and_scope(fixtures):
    state = CaseState(Session(customer_id="alice", identity_verified=True, consented_order_ids=frozenset({"1043"})), *fixtures)
    calculate_refund(state, "1042")
    with pytest.raises(ToolDenied, match="consent"):
        issue_refund(state, "1042", Decimal("99.00"))
    assert not state.ledger


def test_ineligible_does_not_mutate(state):
    calculate_refund(state, "1047")
    with pytest.raises(ToolDenied, match="not eligible"):
        issue_refund(state, "1047", Decimal("0.00"))
    assert not state.ledger
