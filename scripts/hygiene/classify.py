import re
from collections import defaultdict
from typing import Dict, List, Optional
from .model import Item, Finding, Severity, Kind, Origin, Host, Usage
from .normalize import norm_mcp_server
from . import memory as _memory

SAFETY_HINTS = ("github", "postgres", "supabase", "aws", "filesystem")  # write-capable / sensitive
SAFETY_SKILL_HINTS = ("security", "vetter", "git-commit")

def _match_usage(item: Item, skill_usage: Dict, mcp_usage: Dict) -> Optional[dict]:
    if item.kind == Kind.SKILL:
        for k in item.match_keys or {item.name}:
            if k in skill_usage:
                return skill_usage[k]
        return None
    if item.kind == Kind.MCP:
        nk = norm_mcp_server(item.name)
        for uname, rec in mcp_usage.items():
            if norm_mcp_server(uname) == nk:
                return rec
        return None
    return None

def _overlap_clusters(items: List[Item]) -> Dict[str, int]:
    """Map item.name -> cluster size for skills sharing a name prefix token (>=3 members)."""
    buckets = defaultdict(list)
    for it in items:
        if it.kind == Kind.SKILL and it.enabled:
            token = re.split(r"[-_:]", it.name)[0].lower()
            buckets[token].append(it.name)
    size = {}
    for token, names in buckets.items():
        if len(names) >= 3:
            for n in names:
                size[n] = len(names)
    return size

def classify(items, skill_usage, mcp_usage, now, window_days) -> List[Finding]:
    findings: List[Finding] = []
    window = window_days * 86400
    overlaps = _overlap_clusters(items)
    mem_dups = _memory.cross_file_duplicates([it for it in items if it.kind == Kind.MEMORY])

    # duplicate detection: same name among ENABLED items
    name_counts = defaultdict(int)
    for it in items:
        if it.enabled and it.kind == Kind.SKILL:
            name_counts[it.name.split(":")[-1]] += 1

    matched_skill_keys, matched_mcp_keys = set(), set()

    for it in items:
        if it.kind == Kind.PLUGIN:
            continue
        # hooks/memory: always-loaded, no usage signal — never auto-green
        if it.kind in (Kind.HOOK, Kind.MEMORY):
            mreasons, msev = [], Severity.KEEP
            if it.kind == Kind.HOOK:
                mreasons.append("always-loaded hook — review manually")
            else:
                mreasons.append("memory file")
                if it.cost_band == "high":
                    mreasons.append(f"large (~{it.est_tokens} lines) — consider trimming/splitting")
                    msev = Severity.YELLOW
                dup = mem_dups.get(it.path)
                if dup:
                    mreasons.append(f"{dup} entries duplicated in other memory files")
                    msev = Severity.YELLOW
            findings.append(Finding(item=it, severity=msev, reasons=mreasons))
            continue
        rec = _match_usage(it, skill_usage, mcp_usage)
        reasons, sev, cmd = [], None, None
        recent = bool(rec and rec.get("last") and (now - rec["last"]) <= window)
        used_ever = bool(rec and rec.get("count"))

        if rec is not None:
            if it.kind == Kind.SKILL:
                matched_skill_keys |= set(it.match_keys or {it.name})
            else:
                matched_mcp_keys.add(norm_mcp_server(it.name))

        # D3 disabled / inactive-on-disk
        if not it.enabled:
            if it.origin == Origin.PLUGIN or it.plugin:   # disabled plugin's cached skill = disk bloat
                reasons.append("disabled plugin on disk (archive candidate)")
                sev = Severity.YELLOW
            else:
                reasons.append("catalog/available — not active")
                sev = Severity.KEEP
        else:
            is_safety = (it.kind == Kind.MCP and any(h in norm_mcp_server(it.name) for h in SAFETY_HINTS)) \
                        or (it.kind == Kind.SKILL and any(h in it.name.lower() for h in SAFETY_SKILL_HINTS))
            if recent:
                reasons.append("actively used"); sev = Severity.KEEP
            elif used_ever:
                reasons.append(f"stale (last use >{window_days}d ago)"); sev = Severity.YELLOW
            else:
                # never used
                if is_safety:
                    reasons.append("never used but write-scoped/safety — review manually")
                    sev = Severity.RED
                elif it.host == Host.CODEX and it.kind == Kind.SKILL:
                    # Codex skill-invocation detection is best-effort; never auto-clean
                    reasons.append("no recorded use (Codex usage is best-effort — verify before removing)")
                    sev = Severity.YELLOW
                else:
                    reasons.append("never used")
                    sev = Severity.GREEN
            # D4 duplicate
            if it.kind == Kind.SKILL and name_counts.get(it.name.split(":")[-1], 0) > 1:
                reasons.append("duplicate name across locations")
                sev = Severity.YELLOW if sev == Severity.KEEP else sev
            # D5 overlap
            if it.name in overlaps:
                reasons.append(f"overlap cluster x{overlaps[it.name]}")
                if sev == Severity.KEEP:
                    sev = Severity.YELLOW
            # D6 heavy + not recent
            if it.kind == Kind.MCP and it.cost_band == "high" and not recent:
                reasons.append("high context cost, low use")
                if sev == Severity.KEEP:
                    sev = Severity.YELLOW

        usage_obj = None
        if rec:
            usage_obj = Usage(name=it.name, count=rec.get("count", 0), last_used=rec.get("last"))
        findings.append(Finding(item=it, severity=sev or Severity.YELLOW,
                                reasons=reasons, usage=usage_obj))

    # D9 orphan skill usage (used but not installed)
    for uname, rec in skill_usage.items():
        if uname not in matched_skill_keys and uname.split(":")[-1] not in {k.split(":")[-1] for k in matched_skill_keys}:
            findings.append(_info_finding("skill", uname, f"orphan usage (invoked {rec.get('count')}x, not installed)"))
    # D10 unmatched MCP usage (used but no config)
    for uname, rec in mcp_usage.items():
        if norm_mcp_server(uname) not in matched_mcp_keys:
            findings.append(_info_finding("mcp", uname, f"unmatched usage (invoked {rec.get('count')}x, no config found)"))
    return findings

def _info_finding(kind, name, reason) -> Finding:
    it = Item(Host.CLAUDE, Kind.SKILL if kind == "skill" else Kind.MCP,
              name, Origin.USER_CONFIG, "(usage-only)", False)
    return Finding(item=it, severity=Severity.KEEP, reasons=[reason])
