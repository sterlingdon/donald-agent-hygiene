import html as _html
from collections import Counter
from .model import Severity

_SEV = [(Severity.GREEN, "🟢 可直接清理"), (Severity.YELLOW, "🟡 需人工判断"),
        (Severity.RED, "🔴 谨慎处理"), (Severity.KEEP, "✅ 保留 / 信息")]


def _row(f):
    it = f.item
    cmd = _html.escape(f.suggested_cmd or "")
    u = f.usage.count if f.usage else 0
    return (f"<tr><td>{_html.escape(it.host.value)}</td><td>{_html.escape(it.kind.value)}</td>"
            f"<td>{_html.escape(it.name)}</td><td>{_html.escape(it.origin.value)}</td>"
            f"<td>{'on' if it.enabled else 'off'}</td><td>{u}</td>"
            f"<td>{_html.escape(it.cost_band)}</td>"
            f"<td>{_html.escape('; '.join(f.reasons))}</td>"
            f"<td><code onclick=\"navigator.clipboard.writeText(this.textContent)\">{cmd}</code></td></tr>")


def render_html(findings, meta) -> str:
    counts = Counter(f.severity for f in findings)
    head = ("<!doctype html><html lang='zh'><head><meta charset='utf-8'>"
            "<title>agent-hygiene report</title><style>"
            "body{font:14px/1.5 -apple-system,sans-serif;background:#0d1117;color:#e6edf3;margin:2rem}"
            "h1{font-size:1.4rem} details{margin:1rem 0;border:1px solid #30363d;border-radius:8px;padding:.5rem 1rem}"
            "summary{cursor:pointer;font-weight:600} table{width:100%;border-collapse:collapse;margin-top:.5rem}"
            "td,th{padding:.35rem .5rem;border-bottom:1px solid #21262d;text-align:left;font-size:13px}"
            "code{background:#161b22;padding:.1rem .3rem;border-radius:4px;cursor:copy;color:#7ee787}"
            ".g{color:#3fb950}.y{color:#d29922}.r{color:#f85149}</style></head><body>")
    summary = (f"<h1>🧹 Agent Hygiene 体检</h1>"
               f"<p>{_html.escape(str(meta.get('host','')))} · {_html.escape(str(meta.get('generated','')))}</p>"
               f"<p><span class='g'>🟢 {counts[Severity.GREEN]}</span> · "
               f"<span class='y'>🟡 {counts[Severity.YELLOW]}</span> · "
               f"<span class='r'>🔴 {counts[Severity.RED]}</span> · ✅ {counts[Severity.KEEP]}</p>")
    body = []
    for sev, label in _SEV:
        rows = [_row(f) for f in findings if f.severity == sev]
        if not rows:
            continue
        body.append(
            f"<details {'open' if sev in (Severity.GREEN, Severity.YELLOW) else ''}>"
            f"<summary>{label} ({len(rows)})</summary>"
            "<table><tr><th>host</th><th>kind</th><th>name</th><th>origin</th><th>on</th>"
            "<th>uses</th><th>cost</th><th>reasons</th><th>cmd</th></tr>"
            + "".join(rows) + "</table></details>")
    return head + summary + "".join(body) + "</body></html>"
