import argparse, os, time, sys
from . import collect_cc, collect_codex, usage_cc, usage_codex, cost, classify, report, actions, state


def _dedup(items):
    """Collapse exact-duplicate inventory entries (e.g. the same plugin MCP cached
    under several versions). Keeps personal-vs-plugin duplicates distinct (different
    origin) so the duplicate-detection rule still fires."""
    seen = {}
    for it in items:
        key = (it.host.value, it.kind.value, it.name, it.origin.value, it.enabled)
        if key not in seen:
            seen[key] = it
    return list(seen.values())


def _build_findings(home, codex_home, projects, sessions, cwd, window_days):
    items = collect_cc.collect(home, cwd=cwd) + collect_codex.collect(codex_home)
    items = _dedup(items)
    for it in items:
        cost.estimate(it)
    sk1, mc1 = usage_cc.collect_usage(projects)
    sk2, mc2 = usage_codex.collect_usage(sessions)
    skills = _merge(sk1, sk2); mcps = _merge(mc1, mc2)
    findings = classify.classify(items, skills, mcps, now=time.time(), window_days=window_days)
    for f in findings:
        f.suggested_cmd = actions.suggest_command(f)
    return findings


def run(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hygiene")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan")
    for opt in ("--home", "--codex-home", "--projects", "--sessions", "--cwd", "--out"):
        s.add_argument(opt, required=True)
    s.add_argument("--window-days", type=int, default=90)

    ap2 = sub.add_parser("apply")
    for opt in ("--home", "--codex-home", "--projects", "--sessions", "--cwd"):
        ap2.add_argument(opt, required=True)
    ap2.add_argument("--backups", default=os.path.expanduser("~/.agent-hygiene-backups"))
    ap2.add_argument("--severity", default="green", choices=["green", "yellow"])
    ap2.add_argument("--kinds", default="skill,mcp")
    ap2.add_argument("--window-days", type=int, default=90)
    ap2.add_argument("--apply", action="store_true")

    sv = sub.add_parser("serve")
    for opt in ("--home", "--codex-home", "--projects", "--sessions", "--cwd"):
        sv.add_argument(opt, required=True)
    sv.add_argument("--backups", default=os.path.expanduser("~/.agent-hygiene-backups"))
    sv.add_argument("--port", type=int, default=8765)
    sv.add_argument("--window-days", type=int, default=90)
    sv.add_argument("--probe", action="store_true", help=argparse.SUPPRESS)

    dg = sub.add_parser("digest")
    dg.add_argument("--state", default=None)

    ih = sub.add_parser("install-hook")
    ih.add_argument("--home", default=os.path.expanduser("~"))
    ih.add_argument("--apply", action="store_true")

    a = ap.parse_args(argv)

    # instant, pipeline-free commands
    if a.cmd == "digest":
        st = state.read_state(a.state or state.default_state_path())
        if not st:
            print("🧹 hygiene: no scan yet — run 'hygiene scan'")
        else:
            print(f"🧹 hygiene: 🟢{st.get('green', 0)} 🟡{st.get('yellow', 0)} "
                  f"(checked {_age(time.time() - st.get('ts', 0))}) — run 'hygiene serve' to clean")
        return 0
    if a.cmd == "install-hook":
        return _install_hook(a)

    findings = _build_findings(a.home, a.codex_home, a.projects, a.sessions, a.cwd, a.window_days)

    if a.cmd == "scan":
        html = report.render_html(findings, meta={
            "host": "claude+codex", "generated": time.strftime("%Y-%m-%d %H:%M")})
        with open(a.out, "w", encoding="utf-8") as fp:
            fp.write(html)
        state.write_state(state.default_state_path(), findings)
        print(f"wrote {a.out}  ({len(findings)} findings)")
        return 0

    if a.cmd == "apply":
        want_kinds = set(a.kinds.split(","))
        selected = [f for f in findings
                    if f.severity.value == a.severity and f.item.kind.value in want_kinds]
        applied = 0
        for f in selected:
            r = actions.execute(f, backups=a.backups, dry_run=not a.apply, home=a.home)
            tag = "APPLIED" if r.applied else "DRY-RUN"
            print(f"[{tag}] {r.kind:14s} {f.item.host.value}/{f.item.kind.value} {f.item.name} :: {r.command}")
            applied += int(r.applied)
        print(f"{'APPLIED' if a.apply else 'DRY-RUN'}: {len(selected)} selected, {applied} mutated"
              + ("" if a.apply else "  (re-run with --apply to execute)"))
        return 0

    # serve
    from . import serve as serve_mod
    httpd, token = serve_mod.build_server(findings, backups=a.backups, home=a.home, port=a.port)
    _host, port = httpd.server_address
    print(f"hygiene report serving on http://127.0.0.1:{port}/   token={token}")
    print("Open in a browser. 'execute' buttons mutate with backup. Ctrl-C to stop.")
    if a.probe:
        httpd.server_close()
        return 0
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


def _age(secs):
    secs = max(0, int(secs))
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def _install_hook(a):
    import json, shutil
    scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hook_cmd = f"cd {scripts_dir} && python -m hygiene.cli digest"
    settings = os.path.join(a.home, ".claude", "settings.json")
    data = {}
    if os.path.isfile(settings):
        try:
            with open(settings) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}
    sessionstart = (data.get("hooks") or {}).get("SessionStart", [])
    if any("hygiene.cli digest" in json.dumps(e) for e in sessionstart):
        print("install-hook: SessionStart digest hook already present — nothing to do")
        return 0
    if not a.apply:
        print(f"[DRY-RUN] would add SessionStart hook to {settings}:\n  {hook_cmd}")
        print("re-run with --apply to install")
        return 0
    os.makedirs(os.path.dirname(settings), exist_ok=True)
    if os.path.isfile(settings):
        shutil.copy2(settings, settings + ".hygiene-bak")
    data.setdefault("hooks", {}).setdefault("SessionStart", []).append(
        {"matcher": "*", "hooks": [{"type": "command", "command": hook_cmd}]})
    with open(settings, "w") as f:
        json.dump(data, f, indent=2)
    print(f"installed SessionStart digest hook into {settings}")
    return 0


def _merge(a, b):
    out = dict(a)
    for k, v in b.items():
        if k in out:
            out[k] = {"count": out[k]["count"] + v["count"],
                      "last": max(filter(None, [out[k]["last"], v["last"]]), default=None)}
        else:
            out[k] = v
    return out


def main():
    sys.exit(run())


if __name__ == "__main__":
    main()
