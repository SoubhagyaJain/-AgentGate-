"""Validated configuration; credentials are never part of trace metadata."""

import os
from typing import Annotated, Mapping, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator

from agentgate.schemas import StrictModel


class AgentConfig(StrictModel):
    model: Annotated[str, Field(min_length=1, max_length=160)] = "qwen3.5:4b-q4_K_M"
    base_url: str = "http://localhost:11434/v1"
    api_key: SecretStr = Field(default_factory=lambda: SecretStr("ollama"), exclude=True, repr=False)
    timeout: Annotated[float, Field(gt=0, le=600)] = 60.0
    temperature: Annotated[float, Field(ge=0, le=2)] = 0.2
    top_p: Annotated[float, Field(gt=0, le=1)] = 1.0
    presence_penalty: Annotated[float, Field(ge=-2, le=2)] = 0.0
    frequency_penalty: Annotated[float, Field(ge=-2, le=2)] = 0.0
    max_tokens: Annotated[int, Field(ge=1, le=4096)] = 1024
    max_turns: Annotated[int, Field(ge=1, le=8)] = 8
    max_tool_invocations: Annotated[int, Field(ge=1, le=12)] = 12
    seed: Annotated[int, Field(ge=0)] | None = None
    reasoning_effort: str | None = None

    @model_validator(mode="after")
    def safe_endpoint(self) -> Self:
        url = urlsplit(self.base_url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Endpoint needs http(s), host and no embedded credentials/query/fragment")
        _ = url.port  # Validate malformed port values.
        local = url.hostname in {"localhost", "127.0.0.1", "::1"}
        if url.scheme == "http" and not local:
            raise ValueError("Credentials over HTTP allowed only on loopback")
        if not self.api_key.get_secret_value() or (not local and self.api_key.get_secret_value() == "ollama"):
            raise ValueError("Hosted endpoint requires an explicit credential")
        if any(c in self.api_key.get_secret_value() for c in "\r\n"):
            raise ValueError("Invalid credential header")
        if not url.path.rstrip("/").endswith("/v1"):
            raise ValueError("Base URL must end in /v1")
        return self

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AgentConfig":
        env = os.environ if env is None else env
        converters = {
            "model": str, "base_url": str, "api_key": SecretStr,
            "timeout": float, "temperature": float, "top_p": float,
            "presence_penalty": float, "frequency_penalty": float,
            "max_tokens": int, "max_turns": int, "max_tool_invocations": int,
            "seed": int, "reasoning_effort": str,
        }
        values = {}
        for name, converter in converters.items():
            variable = "AGENTGATE_" + name.upper()
            if variable in env:
                try:
                    values[name] = converter(env[variable])
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"Invalid {variable}") from exc
        return cls(**values)

    def public_dict(self) -> dict:
        return self.model_dump(mode="json")
