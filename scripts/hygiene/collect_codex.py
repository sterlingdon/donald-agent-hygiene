import os
from typing import List
from .model import Item, Kind, Host, Origin
from .util import read_frontmatter, read_toml
from .normalize import skill_match_keys

# active skill roots vs catalog/cache/tmp (inactive)
def _origin_for(md_path: str):
    """
    Classify a SKILL.md path to (origin, enabled) or None to skip.
    Returns None for non-user-manageable system skills.
    """
    low = md_path.lower()
    if f"{os.sep}skills{os.sep}.system{os.sep}" in low:
        return None  # Skip system skills entirely
    if f"{os.sep}plugins{os.sep}cache{os.sep}" in low:
        return Origin.PLUGIN, True
    if ".curated" in low or "vendor_imports" in low:
        return Origin.CATALOG, False
    if f"{os.sep}.tmp{os.sep}" in low or "legacy-" in low:
        return Origin.CATALOG, False
    return Origin.PERSONAL, True

def _find_skill_mds(root: str):
    """Yield all SKILL.md paths under root, including hidden subdirectories."""
    for dirpath, _dirs, files in os.walk(root):
        if "SKILL.md" in files:
            yield os.path.join(dirpath, "SKILL.md")

def collect(codex_home: str) -> List[Item]:
    if not os.path.isdir(codex_home):
        return []
    items: List[Item] = []
    # S5/S6/S7 skills (skills/, superpowers/skills/, vendor_imports curated, .tmp legacy)
    for md in _find_skill_mds(codex_home):
        result = _origin_for(md)
        if result is None:
            continue  # Skip non-user-manageable skills
        origin, enabled = result
        sd = os.path.dirname(md)
        fm = read_frontmatter(md)
        name = fm.get("name") or os.path.basename(sd)
        items.append(Item(Host.CODEX, Kind.SKILL, name, origin, sd, enabled,
                          description=fm.get("description", ""),
                          match_keys=frozenset(set(skill_match_keys(name)) | {os.path.basename(sd)})))
    # M4 MCP from config.toml
    cfg = read_toml(os.path.join(codex_home, "config.toml"))
    for name in (cfg.get("mcp_servers") or {}):
        items.append(Item(Host.CODEX, Kind.MCP, name, Origin.USER_CONFIG,
                          os.path.join(codex_home, "config.toml"), True))
    # ME2 memory: AGENTS.md, memories/, rules/
    for name in ("AGENTS.md", "memories", "rules"):
        p = os.path.join(codex_home, name)
        if os.path.exists(p):
            items.append(Item(Host.CODEX, Kind.MEMORY, name, Origin.USER_CONFIG, p, True))
    # HK3 hooks in config.toml
    if cfg.get("hooks"):
        items.append(Item(Host.CODEX, Kind.HOOK, "config.toml:hooks", Origin.USER_CONFIG,
                          os.path.join(codex_home, "config.toml"), True))
    return items
