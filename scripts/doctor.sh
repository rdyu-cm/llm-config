#!/usr/bin/env bash
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
failures=0

find_python() {
  for candidate in "${PYTHON:-}" python3 "$HOME"/.local/share/uv/python/cpython-3.*/bin/python3; do
    if [ -n "$candidate" ] && command -v "$candidate" >/dev/null 2>&1 && \
       "$candidate" -c 'import tomllib' >/dev/null 2>&1; then
      echo "$candidate"
      return
    fi
  done
  return 1
}

PYTHON=$(find_python || true)

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
if [ -n "$PYTHON" ]; then
  echo "ok      Python 3.11+: $PYTHON"
else
  echo "missing Python 3.11+ (required)" >&2
  failures=$((failures + 1))
fi
check_command "Node.js" node true
check_command "npx" npx true
check_command "GitHub CLI" gh false
if npx -y codebase-memory-mcp@0.8.1 </dev/null; then
  echo "ok      Codebase Memory MCP"
else
  echo "broken  Codebase Memory MCP" >&2
  failures=$((failures + 1))
fi

if [ -n "$PYTHON" ] && "$PYTHON" "$ROOT/scripts/validate.py"; then
  echo "ok      repository configuration"
else
  failures=$((failures + 1))
fi

if [ -L "$HOME/.codex/config.toml" ] && \
   [ "$(readlink "$HOME/.codex/config.toml")" = "$ROOT/.codex/config.generated.toml" ]; then
  if [ -n "$PYTHON" ] && "$PYTHON" "$ROOT/scripts/sync_config.py" \
    --base "$ROOT/.codex/config.toml" \
    --local "$HOME/.codex/config.local.toml" \
    --output "$ROOT/.codex/config.generated.toml" \
    --check; then
    echo "ok      global config uses portable base plus local overlay"
  else
    failures=$((failures + 1))
  fi
else
  echo "optional global merged config is not installed"
fi

if [ -n "$PYTHON" ] && (
  cd "$ROOT" && "$PYTHON" -m unittest discover -s tests -p 'test_*.py'
); then
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
