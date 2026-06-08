import argparse, time, sys
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


def run(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hygiene")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--home", required=True)
    s.add_argument("--codex-home", required=True)
    s.add_argument("--projects", required=True)
    s.add_argument("--sessions", required=True)
    s.add_argument("--cwd", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--window-days", type=int, default=90)
    args = ap.parse_args(argv)

    items = collect_cc.collect(args.home, cwd=args.cwd) + collect_codex.collect(args.codex_home)
    items = _dedup(items)
    for it in items:
        cost.estimate(it)
    sk1, mc1 = usage_cc.collect_usage(args.projects)
    sk2, mc2 = usage_codex.collect_usage(args.sessions)
    skills = _merge(sk1, sk2); mcps = _merge(mc1, mc2)

    findings = classify.classify(items, skills, mcps, now=time.time(), window_days=args.window_days)
    for f in findings:
        f.suggested_cmd = actions.suggest_command(f)
    html = report.render_html(findings, meta={
        "host": "claude+codex", "generated": time.strftime("%Y-%m-%d %H:%M")})
    with open(args.out, "w", encoding="utf-8") as fp:
        fp.write(html)
    print(f"wrote {args.out}  ({len(findings)} findings)")
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
