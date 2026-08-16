#!/usr/bin/env bash
# Runs a headless Boy Scout session against the current project's open
# backlog. Intended to be invoked on a schedule (cron, launchd, or
# Superpowers' schedule/loop skill) — see README.md "Scheduled Resolution".
#
# Usage:
#   CLAUDE_PROJECT_DIR=/path/to/project ./scripts/run-boy-scout-session.sh
#
# Always exits 0 (an empty backlog is not an error), so it's safe to wire
# into cron without extra error handling. -e is deliberately omitted:
# boy_scout_session.py exits 1 for "nothing to do", which is expected, not
# a failure — the trap below normalizes that to a clean cron exit.
set -uo pipefail
trap 'exit 0' EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

if ! command -v claude >/dev/null 2>&1; then
  echo "Boy Scout: 'claude' CLI not found on PATH. Skipping session." >&2
  exit 0
fi

cd "$PROJECT_DIR"
python3 "$SCRIPT_DIR/boy_scout_session.py" --project-dir "$PROJECT_DIR"
