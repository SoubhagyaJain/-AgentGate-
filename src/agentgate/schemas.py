"""Strict domain and trajectory contracts. Money crosses JSON boundaries as text."""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel, BeforeValidator, ConfigDict, Field, JsonValue, WithJsonSchema, model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")]


def money_input(value: object) -> Decimal:
    if isinstance(value, str) and re.fullmatch(r"\d{1,9}\.\d{2}", value):
        value = Decimal(value)
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("Money must be a finite Decimal or a two-decimal string")
    if value < 0 or value > Decimal("999999999.99") or value.as_tuple().exponent != -2:
        raise ValueError("Money must be nonnegative, bounded and expressed in cents")
    return value


def rate_input(value: object) -> Decimal:
    if isinstance(value, str) and re.fullmatch(r"(?:0(?:\.\d{1,6})?|1(?:\.0{1,6})?)", value):
        value = Decimal(value)
    if not isinstance(value, Decimal) or not value.is_finite() or not 0 <= value <= 1:
        raise ValueError("Rate must be a finite Decimal between zero and one")
    return value


Money = Annotated[Decimal, BeforeValidator(money_input), WithJsonSchema({"type": "string", "pattern": r"^\d{1,9}\.\d{2}$"})]
Rate = Annotated[Decimal, BeforeValidator(rate_input)]
ClaimField = Literal[
    "return_window_days", "restocking_rate", "shipping_refundable",
    "redeemed_digital_refundable", "order_id", "delivery_status", "kind",
    "item_price", "discount", "tax_paid", "shipping", "paid_amount",
    "purchase_date", "delivery_date", "opened", "defective", "redeemed",
    "eligible", "refund_amount", "reason", "refund_id", "refund_status",
]


class Fact(StrictModel):
    subject: Identifier
    field: ClaimField
    value: str | int | bool

    @model_validator(mode="after")
    def typed_value(self) -> Self:
        if self.field in {"shipping_refundable", "redeemed_digital_refundable", "opened", "defective", "redeemed", "eligible"}:
            if type(self.value) is not bool:
                raise ValueError("Boolean fact required")
        elif self.field == "return_window_days":
            if type(self.value) is not int or not 0 <= self.value <= 365:
                raise ValueError("Integer day count required")
        elif self.field in {"item_price", "discount", "tax_paid", "shipping", "paid_amount", "refund_amount"}:
            if not isinstance(self.value, str):
                raise ValueError("Money fact must be a string")
            money_input(self.value)
        elif self.field == "restocking_rate":
            if not isinstance(self.value, str):
                raise ValueError("Rate fact must be a string")
            rate_input(self.value)
        else:
            if not isinstance(self.value, str) or not 0 < len(self.value) <= 160:
                raise ValueError("Bounded text fact required")
            if self.field in {"purchase_date", "delivery_date"}:
                date.fromisoformat(self.value)
            choices = {
                "delivery_status": {"unshipped", "delivered", "in_transit"},
                "kind": {"physical", "digital"},
                "refund_status": {"issued"},
                "reason": {"unshipped_cancellation", "within_window", "digital_unredeemed", "digital_redeemed_allowed", "digital_redeemed", "window_expired", "in_transit", "already_refunded", "nothing_paid"},
            }
            if self.field in choices and self.value not in choices[self.field]:
                raise ValueError("Unsupported categorical fact")
        return self


class Claim(Fact):
    evidence_ids: Annotated[tuple[str, ...], Field(min_length=1, max_length=8)]


class Evidence(StrictModel):
    evidence_id: Annotated[str, Field(min_length=1, max_length=180)]
    source: Literal["policy", "order", "calculation", "receipt"]
    facts: tuple[Fact, ...]


class FinalAnswer(StrictModel):
    outcome: Literal["policy_answer", "eligible", "ineligible", "refund_issued", "authorization_required", "not_found", "retry_exhausted"]
    claims: Annotated[tuple[Claim, ...], Field(max_length=32)]


class Session(StrictModel):
    customer_id: Identifier
    identity_verified: bool
    consented_order_ids: frozenset[Identifier] = frozenset()


class Order(StrictModel):
    order_id: Identifier
    customer_id: Identifier
    purchase_date: date
    delivery_date: date | None = None
    delivery_status: Literal["unshipped", "delivered", "in_transit"]
    kind: Literal["physical", "digital"] = "physical"
    item_price: Money
    discount: Money
    tax_paid: Money
    shipping: Money
    opened: bool = False
    defective: bool = False
    redeemed: bool = False
    notes: Annotated[str, Field(max_length=1000)] = ""

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.discount > self.item_price:
            raise ValueError("Discount exceeds price")
        if (self.delivery_status == "delivered") != (self.delivery_date is not None):
            raise ValueError("Delivered orders require exactly one delivery date")
        if self.delivery_date is not None and self.delivery_date < self.purchase_date:
            raise ValueError("Delivery predates purchase")
        # Ensure totals stay within the public monetary schema.
        money_input(self.paid_amount)
        return self

    @property
    def discounted_item_price(self) -> Decimal:
        return self.item_price - self.discount

    @property
    def paid_amount(self) -> Decimal:
        return self.discounted_item_price + self.tax_paid + self.shipping


class PolicyRules(StrictModel):
    return_window_days: Annotated[int, Field(ge=0, le=365)] = 30
    restocking_rate: Rate = Decimal("0.20")
    shipping_refundable: bool = False
    redeemed_digital_refundable: bool = False


class PolicyDocument(StrictModel):
    policy_id: Identifier
    version: Identifier
    text: Annotated[str, Field(min_length=1, max_length=4000)]
    facts: tuple[Fact, ...]


class PolicyFixture(StrictModel):
    evaluation_date: date
    rules: PolicyRules
    documents: Annotated[tuple[PolicyDocument, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def consistent_facts(self) -> Self:
        seen: set[str] = set()
        declared: set[str] = set()
        for doc in self.documents:
            if doc.policy_id in seen:
                raise ValueError("Duplicate policy identifier")
            seen.add(doc.policy_id)
            for fact in doc.facts:
                if fact.subject != doc.policy_id:
                    raise ValueError("Policy fact subject mismatch")
                if fact.field not in PolicyRules.model_fields:
                    raise ValueError("Unsupported policy fact")
                expected = getattr(self.rules, fact.field)
                if isinstance(expected, Decimal):
                    expected = str(expected)
                if type(fact.value) is not type(expected) or fact.value != expected:
                    raise ValueError("Policy facts conflict with calculation rules")
                declared.add(fact.field)
        if declared != set(PolicyRules.model_fields):
            raise ValueError("Every policy rule needs an evidence fact")
        return self


class OrdersFixture(StrictModel):
    orders: tuple[Order, ...]

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({o.order_id for o in self.orders}) != len(self.orders):
            raise ValueError("Duplicate order identifier")
        return self


class SearchArguments(StrictModel):
    query: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def nonblank(self) -> Self:
        if not self.query.strip():
            raise ValueError("Empty query")
        return self


class OrderArguments(StrictModel):
    order_id: Identifier


class IssueArguments(OrderArguments):
    amount: Money


class PolicyPassage(StrictModel):
    policy_id: Identifier
    version: Identifier
    document_hash: str
    text: str
    evidence_id: str
    facts: tuple[Fact, ...]


class SearchResult(StrictModel):
    passages: tuple[PolicyPassage, ...]


class OrderView(StrictModel):
    order: Order
    account_verified: bool
    paid_amount: Money


class RefundCalculation(StrictModel):
    order_id: Identifier
    eligible: bool
    amount: Money
    deduction: Money
    tax_refund: Money
    reason: str
    evaluation_date: date
    policy_hash: str


class RefundReceipt(StrictModel):
    order_id: Identifier
    amount: Money
    refund_id: Identifier
    status: Literal["issued"] = "issued"


class ErrorInfo(StrictModel):
    kind: Literal["validation", "authorization", "business", "infrastructure", "protocol", "limit", "answer"]
    code: str
    message: str
    retryable: bool = False


class ToolResponse(StrictModel):
    status: Literal["ok", "denied", "invalid", "error"]
    data: SearchResult | OrderView | RefundCalculation | RefundReceipt | None = None
    evidence: tuple[Evidence, ...] = ()
    error: ErrorInfo | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.status == "ok" and (self.data is None or self.error is not None):
            raise ValueError("Successful tool requires data and no error")
        if self.status != "ok" and (self.data is not None or self.evidence or self.error is None):
            raise ValueError("Failed tool requires error and no data/evidence")
        return self


# Providers may add metadata fields. Preserve them in raw output, not domain schemas.
class ProviderModel(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)


class FunctionCall(ProviderModel):
    name: Annotated[str, Field(min_length=1, max_length=128)]
    arguments: Annotated[str, Field(max_length=8192)]


class ToolCall(ProviderModel):
    id: Annotated[str, Field(min_length=1, max_length=80)]
    type: Literal["function"] = "function"
    function: FunctionCall


class ProviderMessage(ProviderModel):
    role: Literal["assistant"]
    content: Annotated[str, Field(max_length=100000)] | None = None
    tool_calls: list[ToolCall] | None = None


class Choice(ProviderModel):
    index: int
    message: ProviderMessage
    finish_reason: str | None = None


class TokenUsage(ProviderModel):
    prompt_tokens: Annotated[int, Field(ge=0)] | None = None
    completion_tokens: Annotated[int, Field(ge=0)] | None = None
    total_tokens: Annotated[int, Field(ge=0)] | None = None


class ChatCompletion(ProviderModel):
    model: str
    choices: Annotated[list[Choice], Field(min_length=1, max_length=1)]
    usage: TokenUsage | None = None
    system_fingerprint: str | None = None
    id: str | None = None


class AgentMessage(StrictModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] | None = None
    tool_call_id: str | None = None

    @model_validator(mode="after")
    def valid_role(self) -> Self:
        if self.role == "tool" and (self.tool_call_id is None or self.content is None):
            raise ValueError("Tool response needs call ID and content")
        if self.role != "tool" and self.tool_call_id is not None:
            raise ValueError("Only tool messages have tool_call_id")
        if self.role != "assistant" and self.tool_calls is not None:
            raise ValueError("Only assistant messages contain tool calls")
        if self.role in {"system", "user"} and self.content is None:
            raise ValueError("Input messages need content")
        return self


class FunctionDefinition(StrictModel):
    name: Literal["search_policy", "get_order", "calculate_refund", "issue_refund"]
    description: Annotated[str, Field(min_length=1, max_length=2000)]
    parameters: dict[str, JsonValue]


class ToolDefinition(StrictModel):
    type: Literal["function"] = "function"
    function: FunctionDefinition


class HTTPAttempt(StrictModel):
    number: Annotated[int, Field(ge=1, le=3)]
    status_code: int | None
    latency_ms: Annotated[float, Field(ge=0)]
    raw_response: str | None = None
    request_id: str | None = None
    error: ErrorInfo | None = None


class ExecutionEvent(StrictModel):
    sequence: int
    kind: Literal["request", "http_attempt", "model_response", "http_retry", "tool_attempted", "tool_denied", "tool_executed", "state_changed", "answer_invalid", "final_answer", "infrastructure_error", "limit"]
    elapsed_ms: Annotated[float, Field(ge=0)]
    call_id: str | None = None
    tool_name: str | None = None
    arguments_raw: str | None = None
    response: ToolResponse | None = None
    error: ErrorInfo | None = None
    http_attempt: HTTPAttempt | None = None
    parsed_response: ChatCompletion | None = None
    request_body: dict[str, JsonValue] | None = None
    latency_ms: Annotated[float, Field(ge=0)] | None = None


class Trajectory(StrictModel):
    schema_version: Literal["1"] = "1"
    run_id: str
    started_at: datetime
    case_id: str | None
    execution_mode: Literal["model", "test_transport"]
    user_request: str
    prompt_version: str
    prompt_hash: str
    effective_prompt_hash: str
    fixture_hash: str
    configuration_hash: str
    tool_definitions_hash: str
    configuration: dict[str, JsonValue]
    model_identifiers: tuple[str, ...]
    messages: tuple[AgentMessage, ...]
    events: tuple[ExecutionEvent, ...]
    evidence: tuple[Evidence, ...]
    ledger: tuple[RefundReceipt, ...]
    final_answer: FinalAnswer | None
    rendered_response: str | None
    status: Literal["completed", "invalid_answer", "limit_exceeded", "infrastructure_error", "protocol_error"]
    failure: ErrorInfo | None
    total_latency_ms: float

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if [e.sequence for e in self.events] != list(range(len(self.events))):
            raise ValueError("Trace events must be contiguous")
        if self.status == "completed":
            if self.final_answer is None or self.rendered_response is None or self.failure is not None:
                raise ValueError("Completed trajectory needs final answer")
        elif self.failure is None:
            raise ValueError("Incomplete trajectory needs a failure")
        return self
