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

for cli in codex claude; do
  if command -v "$cli" >/dev/null 2>&1; then
    echo "ok      $cli CLI: $(command -v "$cli")"
  else
    echo "optional $cli CLI not installed; that provider will be skipped"
  fi
done

if "$PYTHON" "$ROOT/scripts/validate.py"; then
  echo "ok      repository configuration"
else
  failures=$((failures + 1))
fi

# Reporting only that a tool is missing leaves the reader to work out the package
# name, which differs from the binary for bubblewrap, and the command, which differs
# per distribution. The hint is omitted rather than guessed when no manager matches.
install_hint() {
  case $1 in
    bwrap) package=bubblewrap ;;
    *) package=$1 ;;
  esac
  if command -v apt-get >/dev/null 2>&1; then
    echo "sudo apt install $package"
  elif command -v dnf >/dev/null 2>&1; then
    echo "sudo dnf install $package"
  elif command -v pacman >/dev/null 2>&1; then
    echo "sudo pacman -S $package"
  elif command -v zypper >/dev/null 2>&1; then
    echo "sudo zypper install $package"
  elif command -v apk >/dev/null 2>&1; then
    echo "sudo apk add $package"
  fi
}

# The sandbox degrades to a warning rather than failing when dependencies are
# missing, so a missing tool is reported as optional rather than as a failure.
case "$(uname -s)" in
  Linux)
    for tool in bwrap socat; do
      if command -v "$tool" >/dev/null 2>&1; then
        echo "ok      sandbox dependency $tool: $(command -v "$tool")"
      else
        echo "optional sandbox dependency $tool is missing; Bash commands will run unsandboxed"
        hint=$(install_hint "$tool")
        if [ -n "$hint" ]; then
          echo "        install with: $hint"
        fi
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

for pair in ".codex/config.toml:Codex" ".claude/settings.json:Claude Code"; do
  if [ -e "$HOME/${pair%%:*}" ]; then
    echo "ok      ${pair##*:} config is installed"
  else
    echo "optional ${pair##*:} config is not installed"
  fi
done

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
