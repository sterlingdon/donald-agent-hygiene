"""Cross-file analysis of memory files (CLAUDE.md / AGENTS.md / memory stores).

Finds the same instruction repeated across multiple memory files — a common source
of bloat and conflicting guidance.
"""


def _entries(path):
    """Normalized, non-trivial lines from a memory file (set). Empty on dir/IO error."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except (OSError, IsADirectoryError):
        return set()
    out = set()
    for ln in lines:
        s = ln.strip().lstrip("-*#").strip()
        if len(s) >= 12 and not s.startswith("```"):
            out.add(s.lower())
    return out


def cross_file_duplicates(memory_items):
    """Return {path: count} for each memory file whose entries also appear in
    at least one OTHER memory file."""
    per = {it.path: _entries(it.path) for it in memory_items}
    paths = list(per)
    res = {}
    for p in paths:
        shared = sum(1 for e in per[p] if any(e in per[q] for q in paths if q != p))
        if shared:
            res[p] = shared
    return res
