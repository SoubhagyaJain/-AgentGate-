import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import pytest
from pydantic import SecretStr

from agentgate.config import AgentConfig
from agentgate.llm_client import AdapterFailure, HTTPResponse, LLMClient, UrllibTransport
from tests.support import ScriptedTransport, completion


def test_timeout_twice_then_success_and_usage():
    transport = ScriptedTransport([TimeoutError(), TimeoutError(), completion({"outcome": "authorization_required", "claims": []}, usage={"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17})])
    waits = []
    result = LLMClient(AgentConfig(), transport, waits.append).complete({"messages": []})
    assert len(result.attempts) == 3
    assert len(waits) == 2
    assert result.completion.usage.total_tokens == 17
    assert result.attempts[0].error.retryable
    assert transport.requests[0][2] == transport.requests[2][2]


def test_exhausted_timeout_is_classified():
    transport = ScriptedTransport([TimeoutError(), TimeoutError(), TimeoutError()])
    with pytest.raises(AdapterFailure) as raised:
        LLMClient(AgentConfig(), transport, lambda _: None).complete({})
    assert len(raised.value.attempts) == 3
    assert raised.value.error.kind == "infrastructure"


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_transient_status_retries(status):
    client = LLMClient(AgentConfig(), ScriptedTransport([HTTPResponse(status, "temporarily unavailable"), completion({"outcome":"authorization_required","claims":[]})]), lambda _: None)
    assert len(client.complete({}).attempts) == 2


@pytest.mark.parametrize("status", [302, 400, 401, 403, 404])
def test_permanent_status_not_retried(status):
    transport = ScriptedTransport([HTTPResponse(status, "error")])
    with pytest.raises(AdapterFailure) as raised:
        LLMClient(AgentConfig(), transport).complete({})
    assert len(transport.requests) == 1
    assert raised.value.error.code == f"http_{status}"


@pytest.mark.parametrize("raw", ["not JSON", '{"model":"m","choices":[]}', '{"model":"m","model":"n"}', '{"choices":null}', '{"model":"m","choices":[{"index":0,"message":{"role":"user","content":"x"}}]}'])
def test_protocol_failures_preserve_raw_without_retry(raw):
    with pytest.raises(AdapterFailure) as raised:
        LLMClient(AgentConfig(), ScriptedTransport([HTTPResponse(200, raw)])).complete({})
    assert raised.value.error.kind == "protocol"
    assert raised.value.attempts[0].raw_response == raw
    assert len(raised.value.attempts) == 1


def test_missing_usage_unknown_provider_metadata_and_redaction():
    config = AgentConfig(api_key=SecretStr("UNIQUE_TEST_SECRET"))
    raw = completion({"outcome":"authorization_required","claims":[]}, extras={"future_metadata":{"echo":"UNIQUE_TEST_SECRET"}})
    result = LLMClient(config, ScriptedTransport([raw])).complete({})
    assert result.completion.usage is None
    assert "future_metadata" in result.attempts[0].raw_response
    assert "UNIQUE_TEST_SECRET" not in result.attempts[0].model_dump_json()
    assert "[REDACTED]" in result.attempts[0].raw_response


def test_real_stdlib_http_wire_and_redirect_refusal():
    seen = []
    response = completion({"outcome":"authorization_required","claims":[]})

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append((self.path, self.headers.get("Authorization"), self.rfile.read(int(self.headers["Content-Length"]))))
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/should-not-be-requested")
                self.end_headers()
            else:
                self.send_response(200)
                self.send_header("x-request-id", "wire-test")
                self.end_headers()
                self.wfile.write(response.body.encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        config = AgentConfig(base_url=base + "/v1")
        result = LLMClient(config).complete({"messages": []})
        assert result.attempts[0].request_id == "wire-test"
        assert seen[0][0] == "/v1/chat/completions"
        assert seen[0][1] == "Bearer ollama"
        assert json.loads(seen[0][2]) == {"messages": []}
        redirected = UrllibTransport().post(base + "/redirect", {"Authorization": "Bearer test"}, b"{}", 2.0)
        assert redirected.status_code == 302
        assert len(seen) == 2
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
