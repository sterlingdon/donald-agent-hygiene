from hygiene.classify import classify
from hygiene.model import Item, Kind, Host, Origin, Severity

NOW = 1_780_000_000.0
DAY = 86400

def _skill(name, origin=Origin.PERSONAL, enabled=True, keys=None, desc=""):
    from hygiene.normalize import skill_match_keys
    return Item(Host.CLAUDE, Kind.SKILL, name, origin, f"/p/{name}", enabled,
                description=desc, match_keys=frozenset(keys or skill_match_keys(name)))

def test_keep_when_recent():                       # D7
    it = _skill("alpha")
    f = _index(classify([it], {"alpha": {"count": 5, "last": NOW - DAY}}, {}, NOW, 90))["alpha"]
    assert f.severity == Severity.KEEP

def test_green_never_used_active():                # D1
    it = _skill("never-used")
    f = _index(classify([it], {}, {}, NOW, 90))["never-used"]
    # B: an unused skill is review-only now (usage detection is signal-limited)
    assert f.severity == Severity.YELLOW and "detection is limited" in " ".join(f.reasons)

def test_yellow_stale():                           # D2
    it = _skill("alpha")
    f = _index(classify([it], {"alpha": {"count": 1, "last": NOW - 200 * DAY}}, {}, NOW, 90))["alpha"]
    assert f.severity == Severity.YELLOW and "stale" in " ".join(f.reasons)

def test_namespaced_usage_matches_plugin_skill():  # N1 end-to-end
    it = _skill("superpowers:brainstorming", origin=Origin.PLUGIN)
    f = _index(classify([it], {"superpowers:brainstorming": {"count": 3, "last": NOW}}, {}, NOW, 90))["superpowers:brainstorming"]
    assert f.severity == Severity.KEEP

def test_duplicate_active_names():                 # D4
    a = _skill("dup", origin=Origin.PERSONAL)
    b = _skill("dup", origin=Origin.PLUGIN)
    fs = classify([a, b], {}, {}, NOW, 90)
    dups = [f for f in fs if "duplicate" in " ".join(f.reasons)]
    assert len(dups) >= 1

def test_overlap_cluster():                        # D5
    items = [_skill("tavily-search"), _skill("tavily-research"), _skill("tavily-extract")]
    fs = classify(items, {}, {}, NOW, 90)
    assert any("overlap" in " ".join(f.reasons) for f in fs)

def test_disabled_plugin_skill_archivable():       # D3
    it = _skill("pw", origin=Origin.CATALOG, enabled=False)
    it.plugin = "playwright@off"
    f = _index(classify([it], {}, {}, NOW, 90))["pw"]
    assert f.severity in (Severity.YELLOW, Severity.GREEN)

def test_red_for_safety_mcp():                     # D8
    it = Item(Host.CLAUDE, Kind.MCP, "github", Origin.USER_CONFIG, "/p", True)
    it.cost_band = "high"
    f = _index(classify([it], {}, {"github": {"count": 0, "last": None}}, NOW, 90))["github"]
    assert f.severity in (Severity.YELLOW, Severity.RED)  # never auto-green for write-scoped

def test_orphan_and_unmatched_usage():             # D9, D10
    fs = classify([], {"ghost-skill": {"count": 2, "last": NOW}},
                  {"ccd_session": {"count": 9, "last": NOW}}, NOW, 90)
    reasons = " ".join(r for f in fs for r in f.reasons)
    assert "orphan" in reasons and "unmatched" in reasons

def _index(findings):
    return {f.item.name: f for f in findings if f.item is not None}
