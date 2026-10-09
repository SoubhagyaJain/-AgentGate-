"""Scripted HTTP transport exclusively for deterministic runtime tests."""

import json

from agentgate.llm_client import HTTPResponse


class ScriptedTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, url, headers, body, timeout):
        self.requests.append((url, headers, body, timeout))
        if not self.responses:
            raise AssertionError("Unexpected extra HTTP request")
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result(json.loads(body)) if callable(result) else result


def tool(name, arguments, call_id):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


def completion(content=None, calls=None, usage=None, finish=None, extras=None):
    if isinstance(content, dict):
        content = json.dumps(content)
    payload = {"id": "reply-1", "model": "scripted-test-model", "choices": [{"index": 0, "message": {"role": "assistant", "content": content, "tool_calls": calls}, "finish_reason": finish or ("tool_calls" if calls else "stop")}]}
    if usage is not None:
        payload["usage"] = usage
    if extras:
        payload.update(extras)
    return HTTPResponse(200, json.dumps(payload), "request-1")


def eligible_answer(call_id="calc", amount="99.00"):
    return {"outcome": "eligible", "claims": [
        {"subject": "1042", "field": "eligible", "value": True, "evidence_ids": [f"tool:{call_id}"]},
        {"subject": "1042", "field": "refund_amount", "value": amount, "evidence_ids": [f"tool:{call_id}"]},
    ]}
