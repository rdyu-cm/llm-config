#!/usr/bin/env bash
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
failures=0

check_command() {
  label=$1
  command_name=$2
  required=$3
  if command -v "$command_name" >/dev/null 2>&1; then
    echo "ok      $label: $(command -v "$command_name")"
  elif [ "$required" = true ]; then
    echo "missing $label (required)" >&2
    failures=$((failures + 1))
  else
    echo "optional $label not found"
  fi
}

echo "Portable Codex doctor"
check_command "Codex" codex true
check_command "Python 3" python3 true
check_command "Node.js" node true
check_command "npx" npx true
check_command "GitHub CLI" gh false
check_command "Codebase Memory binary" codebase-memory-mcp false

if python3 "$ROOT/scripts/validate.py"; then
  echo "ok      repository configuration"
else
  failures=$((failures + 1))
fi

if python3 -m unittest discover -s "$ROOT/tests" -p 'test_*.py'; then
  echo "ok      hook contract tests"
else
  failures=$((failures + 1))
fi

if [ -n "${GITHUB_PAT_TOKEN:-}" ]; then
  echo "ok      GITHUB_PAT_TOKEN is set (value not inspected)"
else
  echo "optional GITHUB_PAT_TOKEN is unset; GitHub MCP should remain disabled"
fi

if [ -L "$ROOT/.agents/skills" ]; then
  echo "ok      repo-local skill discovery link"
else
  echo "missing $ROOT/.agents/skills discovery link" >&2
  failures=$((failures + 1))
fi

if [ "$failures" -ne 0 ]; then
  echo "doctor found $failures required problem(s)" >&2
  exit 1
fi

echo "doctor passed"

