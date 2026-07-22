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

GSTACK_STATE="$HOME/.codex/gstack-managed.json"
if [ -e "$GSTACK_STATE" ] || [ -L "$GSTACK_STATE" ]; then
  if [ -L "$GSTACK_STATE" ] || [ ! -f "$GSTACK_STATE" ]; then
    echo "invalid managed state" >&2
    failures=$((failures + 1))
  elif [ -z "$PYTHON" ]; then
    echo "gstack managed state cannot be checked without Python 3.11+" >&2
    failures=$((failures + 1))
  elif mode=$("$PYTHON" -c '
import json
import sys
import tomllib
from pathlib import Path

state_path, root, home = map(Path, sys.argv[1:])
try:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise ValueError("state root is not an object")
    mode = state.get("mode")
    if state.get("version") != 1 or mode not in {"off", "workflow", "full"}:
        raise ValueError("invalid version or mode")
    links = state.get("links")
    if not isinstance(links, dict) or not all(
        isinstance(target, str) and isinstance(source, str)
        for target, source in links.items()
    ):
        raise ValueError("invalid links")
    with (root / "gstack-capabilities.toml").open("rb") as handle:
        catalog = tomllib.load(handle)
except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, tomllib.TOMLDecodeError):
    print("invalid managed state", file=sys.stderr)
    raise SystemExit(1)

expected = {}
if mode != "off":
    skills = catalog["profiles"][mode]["skills"]
    expected = {
        home / ".codex" / "skills" / name: root / "generated" / "gstack-codex" / name
        for name in skills
    }
    runtime = home / ".codex" / "skills" / "gstack"
    expected.update({
        runtime / "bin": root / "vendor" / "gstack" / "bin",
        runtime / "ETHOS.md": root / "vendor" / "gstack" / "ETHOS.md",
        runtime / "review": root / "vendor" / "gstack" / "review",
    })
    if mode == "full":
        expected.update({
            runtime / "browse": root / "vendor" / "gstack" / "browse",
            runtime / "qa": root / "vendor" / "gstack" / "qa",
            runtime / "design": root / "vendor" / "gstack" / "design",
            runtime / "make-pdf": root / "vendor" / "gstack" / "make-pdf",
        })
mismatches = []
if set(links) != {str(target) for target in expected}:
    mismatches.extend(sorted(set(links) ^ {str(target) for target in expected}))
for target, source in expected.items():
    if links.get(str(target)) != str(source) or not source.exists() or not target.is_symlink() or target.resolve() != source.resolve():
        mismatches.append(str(target))
for target in sorted(set(mismatches)):
    print(f"gstack managed link mismatch: {target}", file=sys.stderr)
if mismatches:
    raise SystemExit(1)
print(mode)
' "$GSTACK_STATE" "$ROOT" "$HOME"); then
    echo "ok      gstack $mode"
  else
    failures=$((failures + 1))
  fi
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
