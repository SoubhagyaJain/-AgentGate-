import json
from pathlib import Path

from agentgate import __main__ as cli
from agentgate.config import AgentConfig
from agentgate.llm_client import LLMClient
from agentgate.schemas import Trajectory
from tests.support import ScriptedTransport, completion

ROOT = Path(__file__).resolve().parents[1]


def arguments():
    return ["Can I get a refund?", "--session", str(ROOT / "data/fixtures/session.example.json"), "--fixtures", str(ROOT / "data/fixtures"), "--prompt", str(ROOT / "prompts/baseline.md")]


def test_validation_only_does_not_contact_model(monkeypatch, capsys):
    monkeypatch.setattr(cli, "LLMClient", lambda _: (_ for _ in ()).throw(AssertionError("Model must not be contacted")))
    assert cli.main(arguments() + ["--validate-only"]) == 0
    assert "model not contacted" in capsys.readouterr().out


def test_invalid_session_rejected_without_exposing_input(tmp_path, monkeypatch, capsys):
    session = tmp_path / "bad.json"
    session.write_text(json.dumps({"customer_id":"alice","identity_verified":True,"secret":"PRIVATE_TEST_VALUE"}), encoding="utf-8")
    monkeypatch.setattr(cli, "LLMClient", lambda _: (_ for _ in ()).throw(AssertionError("Model must not be contacted")))
    args = arguments()
    args[args.index("--session")+1] = str(session)
    assert cli.main(args) == 3
    assert "PRIVATE_TEST_VALUE" not in capsys.readouterr().err


def test_request_cli_persists_labeled_test_trace(tmp_path, monkeypatch):
    client = LLMClient(AgentConfig(), ScriptedTransport([completion({"outcome":"authorization_required","claims":[]})]))
    monkeypatch.setattr(cli, "LLMClient", lambda _: client)
    output = tmp_path / "trace.json"
    assert cli.main(arguments() + ["--output", str(output)]) == 0
    trace = Trajectory.model_validate_json(output.read_text(encoding="utf-8"))
    assert trace.execution_mode == "test_transport"


def test_failed_request_still_persists_trace(tmp_path, monkeypatch):
    client = LLMClient(AgentConfig(), ScriptedTransport([TimeoutError(), TimeoutError(), TimeoutError()]), lambda _: None)
    monkeypatch.setattr(cli, "LLMClient", lambda _: client)
    output = tmp_path / "trace.json"
    assert cli.main(arguments() + ["--output", str(output)]) == 2
    assert Trajectory.model_validate_json(output.read_text(encoding="utf-8")).status == "infrastructure_error"


def test_existing_output_rejected_before_network(tmp_path, monkeypatch):
    output = tmp_path / "trace.json"
    output.write_text("original", encoding="utf-8")
    monkeypatch.setattr(cli, "LLMClient", lambda _: (_ for _ in ()).throw(AssertionError("Model must not be contacted")))
    assert cli.main(arguments() + ["--output", str(output)]) == 3
    assert output.read_text(encoding="utf-8") == "original"


def test_trace_persistence_failure_is_not_success(tmp_path, monkeypatch):
    client = LLMClient(AgentConfig(), ScriptedTransport([completion({"outcome":"authorization_required","claims":[]})]))
    monkeypatch.setattr(cli, "LLMClient", lambda _: client)
    monkeypatch.setattr(cli, "save_trace", lambda *_: (_ for _ in ()).throw(OSError("disk full")))
    assert cli.main(arguments() + ["--output", str(tmp_path / "trace.json")]) == 3
