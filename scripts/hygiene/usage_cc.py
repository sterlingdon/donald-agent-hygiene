import glob, json, os
from collections import defaultdict
from typing import Dict, Tuple
from .normalize import parse_mcp_tool
from .util import iso_to_epoch

def _blank():
    return {"count": 0, "last": None}

def _bump(d, key, ts):
    e = d[key]
    e["count"] += 1
    if ts and (e["last"] is None or ts > e["last"]):
        e["last"] = ts

def _record_ts(rec):
    return iso_to_epoch(rec.get("timestamp", "")) if isinstance(rec.get("timestamp"), str) else None

def collect_usage(projects_root: str) -> Tuple[Dict, Dict]:
    """Aggregate skill + MCP-server invocation counts/last-used from CC transcripts.
    Returns (skills, mcps) each: name -> {'count', 'last'}. Builtins excluded (N3)."""
    skills = defaultdict(_blank)
    mcps = defaultdict(_blank)
    for fp in glob.glob(os.path.join(projects_root, "**", "*.jsonl"), recursive=True):
        try:
            fmtime = os.path.getmtime(fp)
        except OSError:
            continue
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("type") != "assistant":
                        continue
                    content = (rec.get("message") or {}).get("content")
                    if not isinstance(content, list):
                        continue
                    ts = _record_ts(rec) or fmtime
                    for b in content:
                        if not isinstance(b, dict) or b.get("type") != "tool_use":
                            continue
                        name = b.get("name")
                        if name == "Skill":
                            sk = (b.get("input") or {}).get("skill")
                            if sk:
                                _bump(skills, sk, ts)
                        elif isinstance(name, str) and name.startswith("mcp__"):
                            parsed = parse_mcp_tool(name)
                            if parsed:
                                _bump(mcps, parsed[0], ts)
        except OSError:
            continue
    return dict(skills), dict(mcps)
