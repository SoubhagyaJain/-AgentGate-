"""No hidden reasoning or evaluator assertions are fabricated here."""

import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from agentgate.schemas import ExecutionEvent, StrictModel, Trajectory


def fingerprint(value: StrictModel | dict | str) -> str:
    if isinstance(value, StrictModel):
        value = value.model_dump(mode="json")
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TraceRecorder:
    def __init__(self) -> None:
        self._events: list[ExecutionEvent] = []

    @property
    def events(self) -> tuple[ExecutionEvent, ...]:
        return tuple(self._events)

    def emit(self, kind: str, **values) -> None:
        self._events.append(ExecutionEvent(sequence=len(self._events), kind=kind, **values))


def save_trace(trajectory: Trajectory, path: Path) -> None:
    """Write UTF-8 JSON atomically; refuse to overwrite immutable run evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(trajectory.model_dump_json(indent=2) + "\n", encoding="utf-8")
        # Linking publishes the complete same-filesystem file atomically and
        # refuses an existing target on both Windows/NTFS and POSIX.
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
