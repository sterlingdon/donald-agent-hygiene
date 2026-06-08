import json
from hygiene.usage_codex import collect_usage

def _ev(ptype, **payload):
    payload["type"] = ptype
    return {"timestamp": "2026-06-08T03:49:48.417Z", "type": "event_msg", "payload": payload}

def test_extracts_mcp_and_skill_calls(tmp_path):
    d = tmp_path / "sessions" / "2026" / "06" / "08"; d.mkdir(parents=True)
    lines = [
        {"timestamp": "x", "type": "session_meta", "payload": {"id": "s1"}},
        _ev("mcp_tool_call", server="neon", tool="run_sql"),
        _ev("function_call", name="codexalpha"),
        _ev("exec_command_begin", command="ls -la"),   # builtin-ish, ignored
    ]
    (d / "rollout-x.jsonl").write_text("\n".join(json.dumps(x) for x in lines))
    skills, mcps = collect_usage(str(tmp_path / "sessions"))
    assert mcps["neon"]["count"] == 1
    assert skills["codexalpha"]["count"] == 1

def test_no_sessions_dir_is_empty(tmp_path):
    skills, mcps = collect_usage(str(tmp_path / "nope"))
    assert skills == {} and mcps == {}
