import json, os
from hygiene.usage_cc import collect_usage

def _rec(name, **inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": inp}]}}

def test_counts_skills_mcps_and_ignores_builtins(tmp_path):
    proj = tmp_path / "projects" / "p1"
    proj.mkdir(parents=True)
    lines = [
        _rec("Skill", skill="tavily-search"),
        _rec("Skill", skill="tavily-search"),
        _rec("Skill", skill="superpowers:brainstorming"),
        _rec("mcp__playwright-extension__browser_click"),
        _rec("Bash", command="ls"),            # N3 builtin ignored
        {"type": "user", "message": {"content": "hi"}},  # non-assistant ignored
    ]
    (proj / "s.jsonl").write_text("\n".join(json.dumps(x) for x in lines))
    skills, mcps = collect_usage(str(tmp_path / "projects"))
    assert skills["tavily-search"]["count"] == 2
    assert skills["superpowers:brainstorming"]["count"] == 1
    assert mcps["playwright-extension"]["count"] == 1
    assert "Bash" not in skills and "Bash" not in mcps

def test_malformed_lines_skipped(tmp_path):
    proj = tmp_path / "projects" / "p"; proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text('{bad\n' + json.dumps(_rec("Skill", skill="x")) + "\n")
    skills, _ = collect_usage(str(tmp_path / "projects"))
    assert skills["x"]["count"] == 1

def test_last_used_uses_record_ts(tmp_path):
    proj = tmp_path / "projects" / "p"; proj.mkdir(parents=True)
    r = _rec("Skill", skill="x"); r["timestamp"] = "2026-06-08T03:49:48.417Z"
    (proj / "s.jsonl").write_text(json.dumps(r))
    skills, _ = collect_usage(str(tmp_path / "projects"))
    assert skills["x"]["last"] is not None
