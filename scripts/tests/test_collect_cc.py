from hygiene.collect_cc import collect
from hygiene.model import Kind, Origin

def _by_name(items, kind):
    return {i.name: i for i in items if i.kind == kind}

def test_skills_cover_personal_plugin_catalog(fake_home):
    items = collect(str(fake_home), cwd=str(fake_home / "noproject"))
    sk = _by_name(items, Kind.SKILL)
    assert sk["alpha"].origin == Origin.PERSONAL and sk["alpha"].enabled is True
    assert sk["never-used"].origin == Origin.PERSONAL
    # plugin skill from ENABLED plugin 'superpowers' -> active, namespaced name available
    bs = sk.get("brainstorming") or sk.get("superpowers:brainstorming")
    assert bs is not None and bs.origin == Origin.PLUGIN and bs.enabled is True
    # catalog skill (marketplace) present but NOT active
    assert sk["pdf"].origin == Origin.CATALOG and sk["pdf"].enabled is False

def test_mcp_user_and_plugin(fake_home):
    items = collect(str(fake_home), cwd=str(fake_home / "noproject"))
    mc = _by_name(items, Kind.MCP)
    assert mc["playwright-extension"].origin == Origin.USER_CONFIG
    assert mc["Framelink Figma MCP"].origin == Origin.USER_CONFIG
    assert mc["neon"].origin == Origin.PLUGIN and mc["neon"].enabled is True

def test_disabled_plugin_skills_not_active(fake_home, tmp_path):
    # add a skill under DISABLED plugin 'playwright@off' -> should be CATALOG/inactive
    import os
    p = f"{fake_home}/.claude/plugins/cache/off/playwright/1.0.0/skills/pw/SKILL.md"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write("---\nname: pw\ndescription: x\n---\nb")
    items = collect(str(fake_home), cwd=str(fake_home / "noproject"))
    pw = [i for i in items if i.name in ("pw", "playwright:pw")][0]
    assert pw.enabled is False
