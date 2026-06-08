"""Tiny cached summary so `digest` (and a SessionStart hook) can report instantly
without re-running the full scan pipeline."""
import json
import os
import time
from collections import Counter


def default_state_path():
    return os.path.expanduser("~/.agent-hygiene-state.json")


def write_state(path, findings):
    c = Counter(f.severity.value for f in findings)
    data = {"green": c.get("green", 0), "yellow": c.get("yellow", 0),
            "red": c.get("red", 0), "total": len(findings), "ts": time.time()}
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass
    return data


def read_state(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
