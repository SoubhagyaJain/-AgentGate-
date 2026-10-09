"""Single-request operator CLI; evaluation and quality gates belong to later phases."""

import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

from agentgate.agent import Agent
from agentgate.config import AgentConfig
from agentgate.exceptions import parse_json
from agentgate.fixtures import load_fixtures
from agentgate.llm_client import LLMClient
from agentgate.schemas import Session
from agentgate.telemetry import save_trace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one synthetic support request; this is not a live evaluation or quality gate.")
    parser.add_argument("query", help="User request (not trusted authorization)")
    parser.add_argument("--session", type=Path, required=True, help="Trusted operator-controlled session JSON; never an end-user upload")
    parser.add_argument("--fixtures", type=Path, default=Path("data/fixtures"))
    parser.add_argument("--prompt", type=Path, default=Path("prompts/baseline.md"))
    parser.add_argument("--output", type=Path, help="New immutable trace path")
    parser.add_argument("--validate-only", action="store_true", help="Validate inputs/configuration without contacting a model")
    args = parser.parse_args(argv)
    try:
        config = AgentConfig.from_env()
        policies, orders = load_fixtures(args.fixtures)
        raw = args.session.read_text(encoding="utf-8")
        if len(raw.encode("utf-8")) > 16000:
            raise ValueError("Session too large")
        session = Session.model_validate_json(json.dumps(parse_json(raw)))
        prompt = args.prompt.read_text(encoding="utf-8")
        if not prompt.strip() or len(prompt) > 16000 or not args.query.strip() or len(args.query) > 4000:
            raise ValueError("Invalid prompt/query length")
        if args.output is not None and args.output.exists():
            raise FileExistsError(args.output)
    except (ValueError, OSError) as exc:
        # No raw validator input or private fixture contents printed.
        print(f"Input/configuration validation failed ({type(exc).__name__}); model not contacted.", file=sys.stderr)
        return 3
    if args.validate_only:
        print("Trusted fixtures/session/configuration validated; model not contacted.")
        return 0
    trajectory = Agent(LLMClient(config)).run(args.query, session, policies, orders, prompt)
    path = args.output or Path("reports") / f"request-{uuid4().hex}.json"
    try:
        save_trace(trajectory, path)
    except OSError:
        print("Trace persistence failed. Do not replay a completed request to repair logging.", file=sys.stderr)
        return 3
    print(f"Trace: {path.resolve()}")
    if trajectory.status != "completed":
        print(f"Request incomplete: {trajectory.failure.code}", file=sys.stderr)
        return 2
    print(trajectory.rendered_response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
