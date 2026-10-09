"""Deterministic lexical retrieval, with versioned passages and facts."""

import re

from agentgate.schemas import PolicyPassage, SearchResult
from agentgate.telemetry.traces import fingerprint
from agentgate.tools.state import CaseState


def search_policy(state: CaseState, query: str) -> SearchResult:
    tokens = set(re.findall(r"[a-z0-9]+", query.lower())) - {"a", "an", "the", "is", "of", "for", "to", "and", "i", "my"}
    ranked = []
    for doc in state.policies.documents:
        words = set(re.findall(r"[a-z0-9]+", (doc.policy_id + " " + doc.text).lower()))
        score = len(tokens & words)
        if score:
            ranked.append((-score, doc.policy_id, doc))
    ranked.sort(key=lambda item: (item[0], item[1]))
    passages = []
    for _, _, doc in ranked[:2]:
        passages.append(PolicyPassage(policy_id=doc.policy_id, version=doc.version, document_hash=fingerprint(doc), text=doc.text, evidence_id=f"policy:{doc.policy_id}:{doc.version}", facts=doc.facts))
    return SearchResult(passages=tuple(passages))
