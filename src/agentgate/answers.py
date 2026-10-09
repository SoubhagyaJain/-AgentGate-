"""Grounded answer validation and deterministic rendering, not scenario scoring."""

from agentgate.schemas import FinalAnswer
from agentgate.tools.state import CaseState

OUTCOMES = {
    "policy_answer": "The retrieved policy states:",
    "eligible": "The order is eligible for a refund.",
    "ineligible": "The order is not eligible for a refund.",
    "refund_issued": "A simulated refund has been issued.",
    "authorization_required": "Additional trusted authorization is required.",
    "not_found": "The order is unavailable for this session.",
    "retry_exhausted": "The task could not be completed after retries.",
}


def validate_answer(answer: FinalAnswer, state: CaseState) -> None:
    for claim in answer.claims:
        for identifier in claim.evidence_ids:
            evidence = state.evidence.get(identifier)
            if evidence is None:
                raise ValueError("Claim cites unavailable evidence")
            if not any(f.subject == claim.subject and f.field == claim.field and type(f.value) is type(claim.value) and f.value == claim.value for f in evidence.facts):
                raise ValueError("Claim is not supported by its cited evidence")
    if answer.outcome in {"policy_answer", "eligible", "ineligible", "refund_issued"} and not answer.claims:
        raise ValueError("Outcome requires factual evidence")
    if answer.outcome in {"eligible", "ineligible"}:
        required = answer.outcome == "eligible"
        if not any(c.field == "eligible" and c.value is required for c in answer.claims):
            raise ValueError("Eligibility outcome requires matching eligibility claim")
    if answer.outcome == "refund_issued":
        if not any(c.field == "refund_id" and c.subject in state.ledger and state.ledger[c.subject].refund_id == c.value for c in answer.claims):
            raise ValueError("Issued outcome requires a real simulated receipt")


def render_answer(answer: FinalAnswer) -> str:
    lines = [OUTCOMES[answer.outcome]]
    for claim in answer.claims:
        value = str(claim.value).lower() if isinstance(claim.value, bool) else str(claim.value)
        lines.append(f"{claim.subject}: {claim.field} = {value} [{', '.join(claim.evidence_ids)}]")
    return "\n".join(lines)
