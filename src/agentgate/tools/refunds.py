"""Explicit deterministic rules; no tool can create consent or real payments."""

from decimal import Decimal, ROUND_HALF_UP

from agentgate.exceptions import ToolDenied
from agentgate.schemas import RefundCalculation, RefundReceipt
from agentgate.telemetry.traces import fingerprint
from agentgate.tools.state import CaseState

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_refund(state: CaseState, order_id: str) -> RefundCalculation:
    order = state.owned_order(order_id)
    rules = state.policies.rules
    amount, deduction, tax = ZERO, ZERO, ZERO
    if order_id in state.ledger:
        reason = "already_refunded"
    elif order.kind == "digital" and order.redeemed and not rules.redeemed_digital_refundable:
        reason = "digital_redeemed"
    elif order.delivery_status == "unshipped":
        amount, tax, reason = order.paid_amount, order.tax_paid, "unshipped_cancellation"
    elif order.delivery_status == "in_transit":
        reason = "in_transit"
    elif (state.policies.evaluation_date - order.delivery_date).days > rules.return_window_days:
        reason = "window_expired"
    else:
        net = order.discounted_item_price
        if order.kind == "physical" and order.opened and not order.defective:
            deduction = cents(net * rules.restocking_rate)
        remaining = net - deduction
        # Paid item tax is prorated by the post-deduction item value. Shipping
        # is stored separately, without shipping tax in these synthetic fixtures.
        tax = cents(order.tax_paid * remaining / net) if net else ZERO
        amount = cents(remaining + tax + (order.shipping if rules.shipping_refundable else ZERO))
        reason = ("digital_redeemed_allowed" if order.redeemed else "digital_unredeemed") if order.kind == "digital" else "within_window"
    if amount == ZERO and reason in {"unshipped_cancellation", "within_window", "digital_unredeemed", "digital_redeemed_allowed"}:
        reason = "nothing_paid"
    result = RefundCalculation(order_id=order_id, eligible=amount > ZERO, amount=amount, deduction=deduction, tax_refund=tax, reason=reason, evaluation_date=state.policies.evaluation_date, policy_hash=state.policy_hash)
    state.remember_calculation(result)
    return result


def issue_refund(state: CaseState, order_id: str, amount: Decimal) -> RefundReceipt:
    state.owned_order(order_id)
    if order_id not in state.session.consented_order_ids:
        raise ToolDenied("consent_required", "Trusted order-scoped consent is required.")
    if order_id in state.ledger:
        raise ToolDenied("already_refunded", "Refund already issued.")
    calculation = state.calculation(order_id)
    if calculation is None or calculation.policy_hash != state.policy_hash:
        raise ToolDenied("calculation_required", "Calculate eligibility before issuing a refund.")
    if not calculation.eligible:
        raise ToolDenied("ineligible", "Order is not eligible for a refund.")
    if amount != calculation.amount:
        raise ToolDenied("amount_mismatch", "Requested amount must match the eligibility calculation.")
    receipt = RefundReceipt(order_id=order_id, amount=amount, refund_id="refund-" + fingerprint({"fixture": state.fixture_hash, "order": order_id})[:16])
    state.add_receipt(receipt)
    return receipt
