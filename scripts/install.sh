#!/usr/bin/env bash
# Single entry point for installing this configuration onto a machine.
#
# Preflights the prerequisites that actually block an install, applies the
# configuration, then verifies the result. Every step it runs is available
# separately; this exists so a new machine needs one command rather than a
# remembered sequence.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
APPLY=true

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) APPLY=false ;;
    -h|--help)
      echo "usage: scripts/install.sh [--dry-run]"
      echo
      echo "Installs this configuration into \$HOME/.claude. With --dry-run,"
      echo "reports what would change without touching the home directory."
      exit 0
      ;;
    *)
      echo "usage: scripts/install.sh [--dry-run]" >&2
      exit 2
      ;;
  esac
  shift
done

fail() {
  echo >&2
  echo "install failed: $1" >&2
  exit 1
}

echo "==> Preflight"

requested=${PYTHON:-}
PYTHON=""
for candidate in "$requested" python3 python3.13 python3.12 python3.11; do
  [ -n "$candidate" ] || continue
  command -v "$candidate" >/dev/null 2>&1 || continue
  if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PYTHON=$candidate
    break
  fi
done
[ -n "$PYTHON" ] || fail "Python 3.11 or newer is required (the validator imports tomllib).
  Debian/Ubuntu: sudo apt install python3.11
  RHEL/Rocky:    sudo dnf install python3.11
  Or point PYTHON at an existing interpreter: PYTHON=/path/to/python3.11 scripts/install.sh"
echo "ok      Python: $(command -v "$PYTHON") ($("$PYTHON" --version 2>&1))"
export PYTHON

if [ "$APPLY" = true ] && ! command -v claude >/dev/null 2>&1; then
  fail "the Claude Code CLI is required before applying, and this repository
  intentionally does not install it. Install Claude Code, then rerun.
  See https://code.claude.com/docs/en/quickstart"
fi
if command -v claude >/dev/null 2>&1; then
  echo "ok      Claude Code: $(command -v claude)"
fi

echo
echo "==> Validate the repository"
"$PYTHON" "$ROOT/scripts/validate.py" || fail "the repository did not validate; nothing was installed."

echo
echo "==> Environment report"
# Advisory only: a missing optional dependency degrades a feature rather than
# blocking the install, so its exit status must not abort the run.
sh "$ROOT/scripts/doctor.sh" || echo "note    doctor reported problems; see above"

echo
if [ "$APPLY" = true ]; then
  echo "==> Apply"
  sh "$ROOT/scripts/bootstrap.sh" --apply || fail "bootstrap could not apply cleanly; resolve the conflicts above and rerun."
else
  echo "==> Dry run"
  sh "$ROOT/scripts/bootstrap.sh" || fail "the dry run reported conflicts; resolve them before applying."
  echo
  echo "Dry run only. Rerun without --dry-run to install."
  exit 0
fi

echo
echo "==> Verify the installed configuration"
status=0
for path in CLAUDE.md hooks agents skills settings.json; do
  target="$HOME/.claude/$path"
  if [ -e "$target" ]; then
    echo "ok      $target"
  else
    echo "missing $target" >&2
    status=1
  fi
done
agents=$(find "$HOME/.claude/agents" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
skills=$(find "$HOME/.claude/skills" -maxdepth 2 -name 'SKILL.md' 2>/dev/null | wc -l | tr -d ' ')
echo "ok      $agents agents and $skills skills are discoverable"
[ "$status" -eq 0 ] || fail "the install completed but the result is incomplete."

echo
echo "Installed. Start a new Claude Code session to pick up the configuration."
echo "This repository must stay at $ROOT; the installed entries are symlinks into it."
