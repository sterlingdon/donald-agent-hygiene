import glob, json, os
from collections import defaultdict
from typing import Dict, Tuple
from .util import iso_to_epoch

# ── Real types confirmed from ~/.codex/sessions rollout-*.jsonl discovery ──
#
# MCP events:
#   mcp_tool_call_end  (697 occurrences) — payload: {invocation: {server, tool, ...}}
#   mcp_tool_call      (plan default, paired "begin" counterpart — kept for forward compat)
#   mcp_call           (plan default alias)
#
# Skill/function-call events:
#   function_call      (64655) — payload: {name, arguments, call_id}
#                      names include exec_command, write_stdin, spawn_agent, view_image, etc.
#   custom_tool_call   (10205) — payload: {name, call_id, ...}
#                      names include apply_patch (only custom tool seen on this machine)
#   tool_call          (plan default — kept for forward compat)
#   tool_search_call   (137)   — skill-search invocations {arguments: {query, limit}}
#                      kept separate; name extracted from arguments.query when present
#
# MCP server/tool field paths (per type):
#   mcp_tool_call_end  → payload.invocation.server  (confirmed: playwright-extension,
#                                                     node_repl, codex_apps, computer-use)
#   mcp_tool_call      → payload.server  (plan default / forward compat)
# ────────────────────────────────────────────────────────────────────────────

# Types whose payload identifies an MCP server invocation
MCP_CALL_TYPES = {"mcp_tool_call", "mcp_call", "mcp_tool_call_end"}

# Types whose payload identifies a skill/function call by name
SKILL_CALL_TYPES = {"function_call", "tool_call", "custom_tool_call"}

# Field names (in order) to extract the skill/function name from a payload
SKILL_NAME_FIELDS = ("name", "skill", "tool")

# Codex builtin function names to exclude from skill usage reporting
CODEX_BUILTIN_FUNCS = {
    "exec_command", "apply_patch", "write_stdin", "view_image", "update_plan",
    "request_user_input", "read_thread_terminal", "spawn_agent", "web_search",
    "kill_command", "read_file", "list_dir", "shell", "container_exec",
    "send_input", "wait", "read_output",
}

# Field names (in order) to extract the MCP server name from a payload.
# For mcp_tool_call_end the server lives in payload.invocation.server — handled specially.
MCP_SERVER_FIELDS = ("server", "server_name")


def _is_builtin(name: str) -> bool:
    """Check if a function name is a Codex builtin (to be excluded from skill usage)."""
    return (not name) or name in CODEX_BUILTIN_FUNCS or name.startswith("browser_")


def _blank():
    return {"count": 0, "last": None}


def _bump(d, key, ts):
    if not key:
        return
    e = d[key]
    e["count"] += 1
    if ts and (e["last"] is None or ts > e["last"]):
        e["last"] = ts


def _first(payload, fields):
    for k in fields:
        v = payload.get(k)
        if isinstance(v, str) and v:
            return v
    return None


def _mcp_server_from_payload(payload: dict):
    """Extract MCP server name from a payload dict.

    For real Codex data the server is nested under ``invocation.server``
    (type ``mcp_tool_call_end``).  For the synthetic test fixtures and
    plan-default types it sits at the top level under ``server`` /
    ``server_name``.  Try both locations.
    """
    # Real: mcp_tool_call_end  → payload.invocation.server
    inv = payload.get("invocation")
    if isinstance(inv, dict):
        s = inv.get("server")
        if isinstance(s, str) and s:
            return s
    # Synthetic / plan defaults → top-level server field
    return _first(payload, MCP_SERVER_FIELDS)


def collect_usage(sessions_root: str) -> Tuple[Dict, Dict]:
    """Aggregate skill + MCP-server invocation counts/last-used from Codex rollout files.

    Returns ``(skills, mcps)`` each ``name -> {'count', 'last'}``.
    Best-effort: unrecognised event types are silently ignored.
    """
    skills: dict = defaultdict(_blank)
    mcps: dict = defaultdict(_blank)

    for fp in glob.glob(
        os.path.join(sessions_root, "**", "rollout-*.jsonl"), recursive=True
    ):
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
                    payload = rec.get("payload") or {}
                    if not isinstance(payload, dict):
                        continue
                    ptype = payload.get("type")
                    ts = iso_to_epoch(rec.get("timestamp", "")) or None

                    if ptype in MCP_CALL_TYPES:
                        _bump(mcps, _mcp_server_from_payload(payload), ts)
                    elif ptype in SKILL_CALL_TYPES:
                        name = _first(payload, SKILL_NAME_FIELDS)
                        if not _is_builtin(name):
                            _bump(skills, name, ts)
        except OSError:
            continue

    return dict(skills), dict(mcps)
