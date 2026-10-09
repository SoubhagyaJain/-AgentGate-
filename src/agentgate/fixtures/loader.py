"""Load trusted files; model/user input must never be passed as a fixture."""

import json
from pathlib import Path

from agentgate.exceptions import parse_json
from agentgate.schemas import OrdersFixture, PolicyFixture


def load_fixtures(directory: Path) -> tuple[PolicyFixture, OrdersFixture]:
    def read(name: str, schema: type):
        raw = (directory / name).read_text(encoding="utf-8")
        if len(raw.encode("utf-8")) > 1_000_000:
            raise ValueError("Fixture too large")
        # Duplicate-key validation first; JSON-mode Pydantic accepts ISO dates.
        return schema.model_validate_json(json.dumps(parse_json(raw)))

    policies = read("policies.json", PolicyFixture)
    orders = read("orders.json", OrdersFixture)
    for order in orders.orders:
        if order.purchase_date > policies.evaluation_date or (order.delivery_date and order.delivery_date > policies.evaluation_date):
            raise ValueError("Fixture order has future dates")
    return policies, orders
