import json

import pytest
from pydantic import ValidationError

from agentgate.fixtures import load_fixtures
from agentgate.schemas import PolicyFixture
from agentgate.tools.policies import search_policy


def test_retrieval_is_deterministic_and_versioned(state):
    first = search_policy(state, "physical opened return window restocking")
    assert first == search_policy(state, "physical opened return window restocking")
    assert first.passages[0].policy_id == "returns-policy"
    assert len(first.passages[0].document_hash) == 64
    assert first.passages[0].version == "v1"
    assert any(f.field == "return_window_days" and f.value == 30 for f in first.passages[0].facts)


def test_no_fabricated_matches(state):
    assert search_policy(state, "zxqv-unused").passages == ()


def test_policy_fact_rule_conflict_rejected(fixtures):
    data = fixtures[0].model_dump(mode="json")
    data["rules"]["return_window_days"] = 7
    with pytest.raises(ValidationError, match="conflict"):
        PolicyFixture.model_validate_json(json.dumps(data))


def test_fixture_loader_rejects_duplicate_keys(tmp_path):
    (tmp_path / "policies.json").write_text('{"rules":{},"rules":{}}', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_fixtures(tmp_path)
