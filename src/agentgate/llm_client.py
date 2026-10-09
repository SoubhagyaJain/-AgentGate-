"""OpenAI-compatible stdlib HTTP client. No production mock or redirect fallback."""

from dataclasses import dataclass
import json
import time
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import ValidationError

from agentgate.config import AgentConfig
from agentgate.exceptions import parse_json
from agentgate.schemas import AgentMessage, ChatCompletion, ErrorInfo, HTTPAttempt, ToolDefinition

MAX_RESPONSE_BYTES = 4_000_000


@dataclass(frozen=True)
class HTTPResponse:
    status_code: int
    body: str
    request_id: str | None = None


class HTTPTransport(Protocol):
    def post(self, url: str, headers: dict[str, str], body: bytes, timeout: float) -> HTTPResponse: ...


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UrllibTransport:
    def __init__(self) -> None:
        self._opener = build_opener(NoRedirect())

    def post(self, url: str, headers: dict[str, str], body: bytes, timeout: float) -> HTTPResponse:
        request = Request(url, data=body, headers=headers, method="POST")
        try:
            response = self._opener.open(request, timeout=timeout)
        except HTTPError as exc:
            response = exc
        with response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("Response size limit exceeded")
            return HTTPResponse(response.status, raw.decode("utf-8"), response.headers.get("x-request-id"))


@dataclass(frozen=True)
class CompletionResult:
    completion: ChatCompletion
    attempts: tuple[HTTPAttempt, ...]


class AdapterFailure(Exception):
    def __init__(self, error: ErrorInfo, attempts: tuple[HTTPAttempt, ...]) -> None:
        self.error = error
        self.attempts = attempts
        super().__init__(error.message)


class LLMClient:
    def __init__(self, config: AgentConfig, transport: HTTPTransport | None = None, sleep: Callable[[float], None] = time.sleep) -> None:
        self.config = config
        # An injected transport is always labeled test evidence, never live evidence.
        self.execution_mode = "model" if transport is None else "test_transport"
        self._transport = UrllibTransport() if transport is None else transport
        self._sleep = sleep

    def request_body(self, messages: tuple[AgentMessage, ...], tools: tuple[ToolDefinition, ...]) -> dict:
        config = self.config
        body = {
            "model": config.model,
            "messages": [m.model_dump(mode="json", exclude_none=True) for m in messages],
            "tools": [t.model_dump(mode="json") for t in tools],
            "tool_choice": "auto", "stream": False, "n": 1,
            "temperature": config.temperature, "top_p": config.top_p,
            "presence_penalty": config.presence_penalty,
            "frequency_penalty": config.frequency_penalty, "max_tokens": config.max_tokens,
        }
        if config.seed is not None:
            body["seed"] = config.seed
        if config.reasoning_effort is not None:
            body["reasoning_effort"] = config.reasoning_effort
        return body

    def _redact(self, value: str | None) -> str | None:
        key = self.config.api_key.get_secret_value()
        if value is None or key == "ollama":
            return value
        return value.replace(json.dumps(key)[1:-1], "[REDACTED]").replace(key, "[REDACTED]")

    def complete(self, body: dict) -> CompletionResult:
        encoded = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        headers = {"Authorization": "Bearer " + self.config.api_key.get_secret_value(), "Content-Type": "application/json"}
        attempts: list[HTTPAttempt] = []
        for number in range(1, 4):
            started = time.perf_counter()
            raw = request_id = None
            status = None
            completion = None
            try:
                response = self._transport.post(self.config.base_url.rstrip("/") + "/chat/completions", headers, encoded, self.config.timeout)
                status, raw, request_id = response.status_code, self._redact(response.body), self._redact(response.request_id)
                if len(response.body.encode("utf-8")) > MAX_RESPONSE_BYTES:
                    raise ValueError("Response size limit exceeded")
                if status != 200:
                    error = ErrorInfo(kind="infrastructure", code=f"http_{status}", message=f"Model endpoint returned HTTP {status}.", retryable=status in {429, 500, 502, 503, 504})
                else:
                    completion = ChatCompletion.model_validate(parse_json(raw))
                    error = None
            except (TimeoutError, OSError, URLError):
                error = ErrorInfo(kind="infrastructure", code="network_error", message="Model transport failed or timed out.", retryable=True)
            except (ValidationError, ValueError, TypeError):
                error = ErrorInfo(kind="protocol", code="invalid_response", message="Endpoint response does not match the chat completion contract.")
            attempt = HTTPAttempt(number=number, status_code=status, latency_ms=(time.perf_counter()-started)*1000, raw_response=raw, request_id=request_id, error=error)
            attempts.append(attempt)
            if error is None:
                return CompletionResult(completion, tuple(attempts))
            if not error.retryable or number == 3:
                raise AdapterFailure(error, tuple(attempts))
            self._sleep(0.05 * number)
        raise AssertionError("Retry loop cannot fall through")
