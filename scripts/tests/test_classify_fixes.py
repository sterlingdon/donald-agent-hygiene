import time
from hygiene.classify import classify
from hygiene.model import Item, Kind, Host, Origin, Severity
from hygiene.normalize import skill_match_keys

NOW = time.time()


def _skill(name, origin=Origin.PERSONAL, host=Host.CLAUDE, plugin=None):
    return Item(host, Kind.SKILL, name, origin, f"/p/{name}", True, plugin=plugin,
                match_keys=frozenset(skill_match_keys(name)))


def test_overlap_ignores_plugin_namespace():
    # 3 distinct skills from ONE plugin must NOT be flagged as an overlap cluster
    items = [_skill("superpowers:a", origin=Origin.PLUGIN, plugin="superpowers@mp"),
             _skill("superpowers:b", origin=Origin.PLUGIN, plugin="superpowers@mp"),
             _skill("superpowers:c", origin=Origin.PLUGIN, plugin="superpowers@mp")]
    fs = classify(items, {}, {}, NOW, 90)
    assert not any("overlap" in " ".join(f.reasons) for f in fs)


def test_overlap_does_not_demote_used_skill():
    # an actively-used personal skill in a naming family stays KEEP (just annotated)
    items = [_skill("tavily-search"), _skill("tavily-research"), _skill("tavily-extract")]
    usage = {"tavily-search": {"count": 5, "last": NOW}}
    fs = classify(items, usage, {}, NOW, 90)
    used = [f for f in fs if f.item.name == "tavily-search"][0]
    assert used.severity == Severity.KEEP
    assert any("overlap" in r for r in used.reasons)        # still annotated
    # the unused siblings are still green
    unused = [f for f in fs if f.item.name == "tavily-research"][0]
    assert unused.severity == Severity.GREEN


def test_plugin_skill_unused_is_yellow_not_green():
    it = _skill("superpowers:rarely-used", origin=Origin.PLUGIN, plugin="superpowers@mp")
    f = [x for x in classify([it], {}, {}, NOW, 90) if x.item is it][0]
    assert f.severity == Severity.YELLOW          # never auto-green a plugin skill
    assert "plugin" in " ".join(f.reasons).lower()


def test_personal_skill_unused_still_green():
    it = _skill("lonely-personal-skill")
    f = [x for x in classify([it], {}, {}, NOW, 90) if x.item is it][0]
    assert f.severity == Severity.GREEN
