import json, re
from datetime import datetime, timezone
from typing import Optional

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

_FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

def read_frontmatter(path: str) -> dict:
    """Parse the leading `--- ... ---` block; capture single-line name/description."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            head = f.read(8192)
    except OSError:
        return {}
    m = _FM.match(head)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out

def read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

def read_toml(path: str) -> dict:
    if tomllib is None:
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, Exception):  # tomllib.TOMLDecodeError subclasses Exception
        return {}

def iso_to_epoch(s: str) -> Optional[float]:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, AttributeError):
        return None
