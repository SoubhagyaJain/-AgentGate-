"""Small exception vocabulary; external errors must not leak private inputs."""

import json
from typing import Any


def parse_json(text: str) -> Any:
    """Reject duplicate keys and non-JSON constants instead of accepting ambiguity."""
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def constant(_: str) -> Any:
        raise ValueError("Non-finite JSON constant")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


class ToolDenied(Exception):
    """A tool rejected the request without disclosing sensitive state."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
