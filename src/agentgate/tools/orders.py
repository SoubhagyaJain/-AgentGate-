"""Order reads are authorized before any fields enter a tool response."""

from agentgate.schemas import OrderView
from agentgate.tools.state import CaseState


def get_order(state: CaseState, order_id: str) -> OrderView:
    order = state.owned_order(order_id)
    return OrderView(order=order, account_verified=True, paid_amount=order.paid_amount)
