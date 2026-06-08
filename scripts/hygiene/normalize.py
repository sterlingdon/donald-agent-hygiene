import re
from typing import Optional, Tuple

def skill_match_keys(name: str) -> set:
    """Keys a usage record might use to refer to this skill. N1."""
    name = (name or "").strip()
    keys = {name}
    if ":" in name:
        keys.add(name.split(":", 1)[1])
    return {k for k in keys if k}

def parse_mcp_tool(tool_full: str) -> Optional[Tuple[str, str]]:
    """'mcp__server__tool' -> ('server','tool'); None if not a 2-part mcp tool. N2."""
    if not isinstance(tool_full, str) or not tool_full.startswith("mcp__"):
        return None
    rest = tool_full[len("mcp__"):]
    server, sep, tool = rest.partition("__")
    if not server or not sep:
        return None
    return server, tool

def norm_mcp_server(raw: str) -> str:
    """Collapse to lowercase alphanumerics so config keys with spaces/case match
    the underscore-joined form seen in `mcp__...` usage. N2."""
    return re.sub(r"[^a-z0-9]", "", (raw or "").lower())
