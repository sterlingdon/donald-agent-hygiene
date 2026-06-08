#!/usr/bin/env bash
set -euo pipefail
HOME_DIR="${HOME}"
OUT="${1:-/tmp/agent-hygiene-report.html}"
cd "$(dirname "$0")"
python -m hygiene.cli scan \
  --home "$HOME_DIR" \
  --codex-home "$HOME_DIR/.codex" \
  --projects "$HOME_DIR/.claude/projects" \
  --sessions "$HOME_DIR/.codex/sessions" \
  --cwd "$PWD" \
  --out "$OUT"
echo "open $OUT"
