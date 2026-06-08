import argparse, os, time, sys
from . import collect_cc, collect_codex, usage_cc, usage_codex, cost, classify, report, actions


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

    a = ap.parse_args(argv)
    findings = _build_findings(a.home, a.codex_home, a.projects, a.sessions, a.cwd, a.window_days)

    if a.cmd == "scan":
        html = report.render_html(findings, meta={
            "host": "claude+codex", "generated": time.strftime("%Y-%m-%d %H:%M")})
        with open(a.out, "w", encoding="utf-8") as fp:
            fp.write(html)
        print(f"wrote {a.out}  ({len(findings)} findings)")
        return 0

    # apply
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
