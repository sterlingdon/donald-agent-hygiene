"""Local one-click-execute server for the hygiene report.

Security invariants:
  * binds 127.0.0.1 only (never 0.0.0.0)
  * a per-process random token gates the mutating POST endpoint
  * the browser confirm()s before any execute
  * actions.execute() always backs up before mutating; Codex MCP stays command-only
"""
import html as _html
import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from . import report, actions
from .model import Severity

_ACTIONABLE_SEV = {Severity.GREEN, Severity.YELLOW}
_ACTIONABLE_KINDS = {"skill", "mcp"}


def actionable_index(findings):
    """(idx, finding) pairs that actions.execute can act on (green/yellow skill/mcp)."""
    return [(i, f) for i, f in enumerate(findings)
            if f.severity in _ACTIONABLE_SEV and f.item.kind.value in _ACTIONABLE_KINDS]


def apply_one(findings, idx, backups, home, dry_run=False):
    return actions.execute(findings[idx], backups=backups, dry_run=dry_run, home=home)


def render_interactive_html(findings, token, meta):
    base = report.render_html(findings, meta)
    rows = ["<h2>⚙️ 一键处置（本地执行，执行前自动备份）</h2>",
            "<table><tr><th>sev</th><th>host/kind</th><th>name</th><th>action</th></tr>"]
    for i, f in actionable_index(findings):
        it = f.item
        rows.append(
            f"<tr><td class='{f.severity.value[0]}'>{f.severity.value}</td>"
            f"<td>{_html.escape(it.host.value)}/{_html.escape(it.kind.value)}</td>"
            f"<td>{_html.escape(it.name)}</td>"
            f"<td><button onclick=\"ah({i})\">execute</button> <span id='r{i}'></span></td></tr>")
    rows.append("</table>")
    js = ("<script>async function ah(i){"
          "if(!confirm('Execute cleanup for #'+i+'?  (a backup is made first)'))return;"
          f"const res=await fetch('/apply?i='+i+'&t={token}',{{method:'POST'}});"
          "const j=await res.json();"
          "document.getElementById('r'+i).textContent="
          "(j.applied?'✅ ':'• ')+(j.kind||'')+' '+(j.backup||j.command||'');}</script>")
    return base.replace("</body></html>", "".join(rows) + js + "</body></html>")


def make_handler(findings, token, backups, home):
    class _Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if urlparse(self.path).path != "/":
                self._send(404, "not found")
                return
            self._send(200, render_interactive_html(
                findings, token, {"host": "claude+codex", "generated": ""}))

        def do_POST(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path != "/apply" or q.get("t", [None])[0] != token:
                self._send(403, json.dumps({"error": "forbidden"}), "application/json")
                return
            try:
                i = int(q.get("i", ["-1"])[0])
            except ValueError:
                i = -1
            if not (0 <= i < len(findings)):
                self._send(400, json.dumps({"error": "bad index"}), "application/json")
                return
            r = apply_one(findings, i, backups, home, dry_run=False)
            self._send(200, json.dumps({
                "applied": r.applied, "kind": r.kind,
                "command": r.command, "backup": r.backup}), "application/json")

        def log_message(self, *a):  # keep the console quiet
            pass

    return _Handler


def build_server(findings, backups, home, port=0):
    """Return (httpd, token). Caller runs httpd.serve_forever(). Binds 127.0.0.1 only."""
    token = secrets.token_urlsafe(8)
    httpd = HTTPServer(("127.0.0.1", port), make_handler(findings, token, backups, home))
    return httpd, token
