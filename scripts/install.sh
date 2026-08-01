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
PASSTHROUGH=""

usage() {
  echo "usage: scripts/install.sh [--dry-run] [--target codex|claude|both] [--adopt]"
  echo
  echo "Installs this configuration into the home directory of one or both"
  echo "providers. With no --target, installs for whichever CLIs are on PATH."
  echo
  echo "  --dry-run  report what would change without touching the home directory"
  echo "  --target   codex, claude, or both"
  echo "  --adopt    repoint links that point into a predecessor checkout of"
  echo "             this configuration; anything unrecognized stays a conflict"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) APPLY=false ;;
    --adopt) PASSTHROUGH="$PASSTHROUGH --adopt" ;;
    --target)
      shift
      [ "$#" -gt 0 ] || { usage >&2; exit 2; }
      case "$1" in
        codex|claude|both) PASSTHROUGH="$PASSTHROUGH --target $1" ;;
        *) usage >&2; exit 2 ;;
      esac
      ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
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

found_cli=false
for cli in codex claude; do
  if command -v "$cli" >/dev/null 2>&1; then
    echo "ok      $cli: $(command -v "$cli")"
    found_cli=true
  fi
done
if [ "$found_cli" = false ]; then
  fail "no Codex or Claude Code CLI was found, and this repository intentionally
  does not install either. Install at least one, then rerun.
  Claude Code: https://code.claude.com/docs/en/quickstart"
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
  sh "$ROOT/scripts/bootstrap.sh" --apply $PASSTHROUGH || fail "bootstrap could not apply cleanly; resolve the conflicts above and rerun."
else
  echo "==> Dry run"
  sh "$ROOT/scripts/bootstrap.sh" $PASSTHROUGH || fail "the dry run reported conflicts; resolve them before applying."
  echo
  echo "Dry run only. Rerun without --dry-run to install."
  exit 0
fi

echo
echo "==> Verify the installed configuration"
status=0
verified=0

# -L is required: the installed entries are symlinks, and find does not descend
# into a symlinked directory without it. Counting zero must fail rather than
# read as a successful install.
verify_provider() {
  label=$1; home=$2; instructions=$3; config=$4; skills_dir=$5
  [ -d "$home" ] || return 0
  verified=$((verified + 1))
  for path in "$instructions" hooks agents "$config"; do
    if [ -e "$home/$path" ]; then
      echo "ok      $home/$path"
    else
      echo "missing $home/$path" >&2
      status=1
    fi
  done
  agents=$(find -L "$home/agents" -maxdepth 1 \( -name '*.md' -o -name '*.toml' \) 2>/dev/null | wc -l | tr -d ' ')
  skills=$(find -L "$skills_dir" -maxdepth 2 -name 'SKILL.md' 2>/dev/null | wc -l | tr -d ' ')
  echo "found   $label: $agents agents and $skills skills"
  [ "$agents" -gt 0 ] || { echo "missing $label has no discoverable agents" >&2; status=1; }
  [ "$skills" -gt 0 ] || { echo "missing $label has no discoverable skills" >&2; status=1; }
}

verify_provider Codex "$HOME/.codex" AGENTS.md config.toml "$HOME/.agents/skills"
verify_provider "Claude Code" "$HOME/.claude" CLAUDE.md settings.json "$HOME/.claude/skills"
[ "$verified" -gt 0 ] || { echo "missing neither provider home exists" >&2; status=1; }
[ "$status" -eq 0 ] || fail "the install completed but the result is incomplete."

echo
echo "Installed. Start a new Claude Code session to pick up the configuration."
echo "This repository must stay at $ROOT; the installed entries are symlinks into it."
