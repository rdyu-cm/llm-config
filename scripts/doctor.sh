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

if PYTHON=$(sh -c '. /dev/stdin' <<'EOF'
for candidate in "${PYTHON:-}" python3 python3.13 python3.12 python3.11; do
  [ -n "$candidate" ] || continue
  command -v "$candidate" >/dev/null 2>&1 || continue
  if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    echo "$candidate"
    exit 0
  fi
done
exit 1
EOF
); then
  echo "ok      Python 3.11+: $(command -v "$PYTHON") ($("$PYTHON" --version 2>&1))"
else
  PYTHON=python3
  echo "missing Python 3.11 or newer (found $(python3 --version 2>&1 || echo none))" >&2
  failures=$((failures + 1))
fi

check_command "Node.js" node
check_command "npx" npx

if command -v claude >/dev/null 2>&1; then
  echo "ok      Claude Code: $(command -v claude)"
else
  echo "optional Claude Code CLI not installed; dry-run and static validation remain available"
fi

if "$PYTHON" "$ROOT/scripts/validate.py"; then
  echo "ok      repository configuration"
else
  failures=$((failures + 1))
fi

# The sandbox degrades to a warning rather than failing when dependencies are
# missing, so a missing tool is reported as optional rather than as a failure.
case "$(uname -s)" in
  Linux)
    for tool in bwrap socat; do
      if command -v "$tool" >/dev/null 2>&1; then
        echo "ok      sandbox dependency $tool: $(command -v "$tool")"
      else
        echo "optional sandbox dependency $tool is missing; Bash commands will run unsandboxed"
      fi
    done
    ;;
  Darwin)
    echo "ok      sandbox uses the built-in macOS sandbox; no extra dependencies"
    ;;
  *)
    echo "optional sandbox dependency check is not implemented for $(uname -s)"
    ;;
esac

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
