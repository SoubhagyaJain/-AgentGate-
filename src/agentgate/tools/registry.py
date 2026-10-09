"""Only the four fixed tools may cross this dispatch boundary."""

import time

from pydantic import ValidationError

from agentgate.exceptions import ToolDenied, parse_json
from agentgate.schemas import (
    ErrorInfo, Evidence, Fact, FunctionDefinition, IssueArguments, OrderArguments,
    OrderView, RefundCalculation, RefundReceipt, SearchArguments, SearchResult,
    ToolCall, ToolDefinition, ToolResponse,
)
from agentgate.telemetry.traces import TraceRecorder
from agentgate.tools.orders import get_order
from agentgate.tools.policies import search_policy
from agentgate.tools.refunds import calculate_refund, issue_refund
from agentgate.tools.state import CaseState

TOOLS = {
    "search_policy": (SearchArguments, "Retrieve fictional policy passages and evidence before answering policy-dependent questions."),
    "get_order": (OrderArguments, "Look up a synthetic order. Requires verified identity and ownership; no existence disclosure on denial."),
    "calculate_refund": (OrderArguments, "Calculate eligibility and exact refund amount under current policy. Does not authorize payment."),
    "issue_refund": (IssueArguments, "Simulated payment only after verification, ownership, trusted order-scoped consent and valid calculation. Amount must be an exact cents string."),
}


class ToolRegistry:
    def __init__(self, state: CaseState, trace: TraceRecorder) -> None:
        self.state = state
        self.trace = trace
        self._seen_ids: set[str] = set()

    @staticmethod
    def definitions() -> tuple[ToolDefinition, ...]:
        return tuple(ToolDefinition(function=FunctionDefinition(name=name, description=description, parameters=schema.model_json_schema())) for name, (schema, description) in TOOLS.items())

    def dispatch(self, call: ToolCall) -> ToolResponse:
        started = time.perf_counter()
        name, raw = call.function.name, call.function.arguments
        self.trace.emit("tool_attempted", call_id=call.id, tool_name=name, arguments_raw=raw)
        error = None
        if call.id in self._seen_ids:
            error = ErrorInfo(kind="protocol", code="duplicate_call_id", message="Tool call identifiers must be unique.")
        self._seen_ids.add(call.id)
        if error is None and name not in TOOLS:
            error = ErrorInfo(kind="validation", code="unknown_tool", message="Unsupported tool name.")
        if error is None:
            try:
                arguments = TOOLS[name][0].model_validate(parse_json(raw))
            except (ValidationError, ValueError, TypeError):
                error = ErrorInfo(kind="validation", code="invalid_arguments", message="Arguments do not match the strict tool schema.")
        if error is not None:
            response = ToolResponse(status="invalid", error=error)
            self.trace.emit("tool_denied", call_id=call.id, tool_name=name, response=response, error=error, latency_ms=(time.perf_counter()-started)*1000)
            return response
        try:
            if name == "search_policy":
                data = search_policy(self.state, arguments.query)
            elif name == "get_order":
                data = get_order(self.state, arguments.order_id)
            elif name == "calculate_refund":
                data = calculate_refund(self.state, arguments.order_id)
            else:
                data = issue_refund(self.state, arguments.order_id, arguments.amount)
        except ToolDenied as exc:
            kind = "authorization" if exc.code in {"access_denied", "consent_required"} else "business"
            error = ErrorInfo(kind=kind, code=exc.code, message=exc.message)
            response = ToolResponse(status="denied", error=error)
            self.trace.emit("tool_denied", call_id=call.id, tool_name=name, response=response, error=error, latency_ms=(time.perf_counter()-started)*1000)
            return response
        evidence = self._evidence_for(call.id, data)
        self.state.remember_evidence(evidence)
        response = ToolResponse(status="ok", data=data, evidence=evidence)
        self.trace.emit("tool_executed", call_id=call.id, tool_name=name, response=response, latency_ms=(time.perf_counter()-started)*1000)
        if isinstance(data, RefundReceipt):
            self.trace.emit("state_changed", call_id=call.id, tool_name=name, response=response)
        return response

    @staticmethod
    def _evidence_for(call_id: str, data) -> tuple[Evidence, ...]:
        if isinstance(data, SearchResult):
            return tuple(Evidence(evidence_id=p.evidence_id, source="policy", facts=p.facts) for p in data.passages)
        if isinstance(data, OrderView):
            order = data.order
            values = {"order_id": order.order_id, "delivery_status": order.delivery_status, "kind": order.kind, "purchase_date": order.purchase_date.isoformat(), "opened": order.opened, "defective": order.defective, "redeemed": order.redeemed, "paid_amount": str(order.paid_amount)}
            for key in ("item_price", "discount", "tax_paid", "shipping"):
                values[key] = str(getattr(order, key))
            if order.delivery_date:
                values["delivery_date"] = order.delivery_date.isoformat()
            source, subject = "order", order.order_id
        elif isinstance(data, RefundCalculation):
            values = {"eligible": data.eligible, "refund_amount": str(data.amount), "reason": data.reason}
            source, subject = "calculation", data.order_id
        else:
            values = {"refund_id": data.refund_id, "refund_status": data.status, "refund_amount": str(data.amount)}
            source, subject = "receipt", data.order_id
        return (Evidence(evidence_id=f"tool:{call_id}", source=source, facts=tuple(Fact(subject=subject, field=key, value=value) for key, value in values.items())),)
