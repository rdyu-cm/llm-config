#!/usr/bin/env bash
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
failures=0

echo "Portable Claude Code doctor"

check_command() {
  label=$1
  command_name=$2
  if command -v "$command_name" >/dev/null 2>&1; then
    echo "ok      $label: $(command -v "$command_name")"
  else
    echo "missing $label ($command_name)" >&2
    failures=$((failures + 1))
  fi
}

check_command "Python 3" python3
check_command "Node.js" node
check_command "npx" npx

if command -v claude >/dev/null 2>&1; then
  echo "ok      Claude Code: $(command -v claude)"
else
  echo "optional Claude Code CLI not installed; dry-run and static validation remain available"
fi

if python3 "$ROOT/scripts/validate.py"; then
  echo "ok      repository configuration"
else
  failures=$((failures + 1))
fi

if [ -e "$HOME/.claude/settings.json" ]; then
  echo "ok      global Claude settings exist"
else
  echo "optional global Claude settings are not installed"
fi

if [ -n "${GITHUB_PAT_TOKEN:-}" ]; then
  echo "ok      GITHUB_PAT_TOKEN is set"
else
  echo "optional GITHUB_PAT_TOKEN is unset; GitHub MCP will not be installed"
fi

if [ "$failures" -ne 0 ]; then
  echo "doctor found $failures required problem(s)" >&2
  exit 1
fi

echo "doctor passed"
