"""Private mutable case-local bookkeeping; trusted inputs stay immutable."""

from types import MappingProxyType

from agentgate.exceptions import ToolDenied
from agentgate.schemas import (
    Evidence, Order, OrdersFixture, PolicyFixture, RefundCalculation, RefundReceipt, Session,
)
from agentgate.telemetry.traces import fingerprint


class CaseState:
    def __init__(self, session: Session, policies: PolicyFixture, orders: OrdersFixture) -> None:
        self._session = session
        self._policies = policies
        self._orders = {o.order_id: o for o in orders.orders}
        for order in orders.orders:
            if order.purchase_date > policies.evaluation_date or (order.delivery_date and order.delivery_date > policies.evaluation_date):
                raise ValueError("Future order date")
        self._calculations: dict[str, RefundCalculation] = {}
        self._ledger: dict[str, RefundReceipt] = {}
        self._evidence: dict[str, Evidence] = {}
        self.fixture_hash = fingerprint({"policies": policies.model_dump(mode="json"), "orders": orders.model_dump(mode="json"), "session": session.model_dump(mode="json")})
        self.policy_hash = fingerprint(policies)

    @property
    def session(self) -> Session:
        return self._session

    @property
    def policies(self) -> PolicyFixture:
        return self._policies

    @property
    def ledger(self):
        return MappingProxyType(self._ledger)

    @property
    def evidence(self):
        return MappingProxyType(self._evidence)

    def owned_order(self, order_id: str) -> Order:
        order = self._orders.get(order_id)
        if not self.session.identity_verified or order is None or order.customer_id != self.session.customer_id:
            # Identical refusal for missing, foreign and unverified orders.
            raise ToolDenied("access_denied", "Order unavailable for this session.")
        return order

    def remember_calculation(self, calculation: RefundCalculation) -> None:
        self._calculations[calculation.order_id] = calculation

    def calculation(self, order_id: str) -> RefundCalculation | None:
        return self._calculations.get(order_id)

    def add_receipt(self, receipt: RefundReceipt) -> None:
        if receipt.order_id in self._ledger:
            raise ToolDenied("already_refunded", "Refund already issued.")
        self._ledger[receipt.order_id] = receipt

    def remember_evidence(self, evidence: tuple[Evidence, ...]) -> None:
        for item in evidence:
            if item.evidence_id in self._evidence and self._evidence[item.evidence_id] != item:
                raise ValueError("Conflicting evidence identifier")
            self._evidence[item.evidence_id] = item
