import json
from hygiene.usage_cc import collect_usage


def _asst(name, **inp):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}}


def test_slash_command_counts_as_skill(tmp_path):
    proj = tmp_path / "projects" / "p"; proj.mkdir(parents=True)
    lines = [
        {"type": "user", "message": {"content": "<command-name>/donald-1person-gitresearch</command-name>"}},
        {"type": "user", "message": {"content": "<command-name>/clear</command-name>"}},   # builtin -> ignored
    ]
    (proj / "s.jsonl").write_text("\n".join(json.dumps(x) for x in lines))
    skills, _ = collect_usage(str(tmp_path / "projects"))
    assert skills["donald-1person-gitresearch"]["count"] == 1
    assert "clear" not in skills


def test_skill_md_read_counts_as_use(tmp_path):
    proj = tmp_path / "projects" / "p"; proj.mkdir(parents=True)
    lines = [
        _asst("Read", file_path="/Users/x/.claude/skills/xiaoyi-renderer/SKILL.md"),
        _asst("Read", file_path="/Users/x/.claude/skills/xiaoyi-renderer/SKILL.md"),
        _asst("Read", file_path="/Users/x/notes.md"),   # non-skill read ignored
    ]
    (proj / "s.jsonl").write_text("\n".join(json.dumps(x) for x in lines))
    skills, _ = collect_usage(str(tmp_path / "projects"))
    assert skills["xiaoyi-renderer"]["count"] == 2
    assert not any("notes" in k for k in skills)
