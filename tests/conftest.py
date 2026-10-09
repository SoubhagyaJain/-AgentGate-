from pathlib import Path

import pytest

from agentgate.fixtures import load_fixtures
from agentgate.schemas import Session
from agentgate.telemetry import TraceRecorder
from agentgate.tools import CaseState, ToolRegistry

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fixtures():
    return load_fixtures(ROOT / "data" / "fixtures")


@pytest.fixture
def session():
    return Session(customer_id="alice", identity_verified=True, consented_order_ids=frozenset({"1042", "1043", "1044", "1046", "1047"}))


@pytest.fixture
def state(fixtures, session):
    return CaseState(session, *fixtures)


@pytest.fixture
def registry(state):
    return ToolRegistry(state, TraceRecorder())
