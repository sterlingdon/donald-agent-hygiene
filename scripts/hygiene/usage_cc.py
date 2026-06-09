import glob, json, os, re
from collections import defaultdict
from typing import Dict, Tuple
from .normalize import parse_mcp_tool
from .util import iso_to_epoch

# Built-in Claude Code slash commands — NOT skills; excluded from usage attribution.
CC_BUILTIN_COMMANDS = {
    "model", "clear", "login", "logout", "status", "compact", "resume", "plugin",
    "plugins", "mcp", "effort", "skills", "reload-plugins", "config", "help", "init",
    "cost", "doctor", "context", "memory", "agents", "vim", "bug", "release-notes",
    "pr-comments", "add-dir", "terminal-setup", "review", "security-review", "ide",
    "exit", "quit", "fast", "resume", "export", "hooks", "permissions", "theme",
}
_CMD_RE = re.compile(r"<command-name>\s*/?([A-Za-z0-9:_-]+)")


def _blank():
    return {"count": 0, "last": None}


def _bump(d, key, ts):
    if not key:
        return
    e = d[key]
    e["count"] += 1
    if ts and (e["last"] is None or ts > e["last"]):
        e["last"] = ts


def _record_ts(rec):
    return iso_to_epoch(rec.get("timestamp", "")) if isinstance(rec.get("timestamp"), str) else None


def _skill_md_name(path):
    """'.../skills/<name>/SKILL.md' or '.../<name>/SKILL.md' -> '<name>'."""
    if isinstance(path, str) and path.endswith("SKILL.md"):
        return os.path.basename(os.path.dirname(path))
    return None


def collect_usage(projects_root: str) -> Tuple[Dict, Dict]:
    """Aggregate skill + MCP-server usage from CC transcripts. A skill counts as used
    via ANY of: an assistant `Skill` tool call, a user slash-command (`<command-name>`),
    or the assistant reading its `SKILL.md`. MCP counted via `mcp__server__tool` calls.
    Built-in tools/commands excluded. Returns (skills, mcps): name -> {'count','last'}."""
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
                    # (1) user slash-command invocations of a skill
                    if "<command-name>" in line:
                        for cmd in _CMD_RE.findall(line):
                            cmd = cmd.strip()
                            if cmd and cmd not in CC_BUILTIN_COMMANDS:
                                _bump(skills, cmd, fmtime)
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
                        inp = b.get("input") or {}
                        if name == "Skill":
                            sk = inp.get("skill")
                            if sk:
                                _bump(skills, sk, ts)
                        elif name == "Read":
                            # (2) reading a skill's SKILL.md is real use of that skill
                            sn = _skill_md_name(inp.get("file_path"))
                            if sn:
                                _bump(skills, sn, ts)
                        elif isinstance(name, str) and name.startswith("mcp__"):
                            parsed = parse_mcp_tool(name)
                            if parsed:
                                _bump(mcps, parsed[0], ts)
        except OSError:
            continue
    return dict(skills), dict(mcps)
