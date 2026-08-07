"""State: remembers episode counter + publish history across runs."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parents[1] / "state" / "state.json"


def load() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"episode": 0, "history": []}


def save(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def record(state: dict, entry: dict) -> None:
    entry = dict(entry)
    entry["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state["history"].append(entry)
