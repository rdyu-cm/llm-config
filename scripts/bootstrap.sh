#!/usr/bin/env bash
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
APPLY=false
action_seen=false
conflicts=0
LOCAL_SETTINGS="$HOME/.claude/settings.local.json"
GENERATED_SETTINGS="$ROOT/.claude/settings.generated.json"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      [ "$action_seen" = false ] || { echo "usage: scripts/bootstrap.sh [--dry-run|--apply]" >&2; exit 2; }
      action_seen=true
      APPLY=false
      ;;
    --apply)
      [ "$action_seen" = false ] || { echo "usage: scripts/bootstrap.sh [--dry-run|--apply]" >&2; exit 2; }
      action_seen=true
      APPLY=true
      ;;
    *)
      echo "usage: scripts/bootstrap.sh [--dry-run|--apply]" >&2
      exit 2
      ;;
  esac
  shift
done

find_python() {
  for candidate in "${PYTHON:-}" python3; do
    if [ -n "$candidate" ] && command -v "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
      return
    fi
  done
  echo "Python 3.11 or newer is required" >&2
  return 1
}

PYTHON=$(find_python)
if [ "$APPLY" = true ] && ! command -v claude >/dev/null 2>&1; then
  echo "Claude Code CLI is required for --apply; install it and rerun." >&2
  exit 1
fi

link_item() {
  source_path=$1
  target_path=$2
  if [ -L "$target_path" ]; then
    current=$(readlink "$target_path")
    if [ "$current" = "$source_path" ]; then
      echo "ok      $target_path"
      return
    fi
    echo "conflict $target_path -> $current" >&2
    return 1
  fi
  if [ -e "$target_path" ]; then
    echo "conflict $target_path already exists; move or merge it manually" >&2
    return 1
  fi
  if [ "$APPLY" = true ]; then
    mkdir -p "$(dirname -- "$target_path")"
    ln -s "$source_path" "$target_path"
    echo "linked  $target_path -> $source_path"
  else
    echo "would   $target_path -> $source_path"
  fi
}

install_settings() {
  target="$HOME/.claude/settings.json"
  merge_local="$LOCAL_SETTINGS"
  preserve_local=false
  if [ -e "$target" ] && [ ! -e "$LOCAL_SETTINGS" ]; then
    merge_local="$target"
    preserve_local=true
    echo "would   preserve existing settings at $LOCAL_SETTINGS"
  elif [ -e "$target" ] && [ -e "$LOCAL_SETTINGS" ]; then
    echo "conflict $target and $LOCAL_SETTINGS both exist; merge them manually" >&2
    return 1
  fi
  if [ "$APPLY" = true ]; then
    "$PYTHON" "$ROOT/scripts/sync_config.py" \
      --base "$ROOT/.claude/settings.json" --local "$merge_local" --output "$GENERATED_SETTINGS"
    if [ "$preserve_local" = true ]; then
      mv "$target" "$LOCAL_SETTINGS"
      echo "local   preserved existing settings at $LOCAL_SETTINGS"
    fi
    mkdir -p "$(dirname -- "$target")"
    cp "$GENERATED_SETTINGS" "$target.tmp"
    mv "$target.tmp" "$target"
    echo "installed $target"
  else
    echo "would   merge portable settings with $LOCAL_SETTINGS"
    echo "would   install merged settings at $target"
  fi
}

install_mcp() {
  if [ "$APPLY" = false ]; then
    echo "would   add user MCP servers: context7, codebase_memory"
    echo "would   add user MCP server github only when GITHUB_PAT_TOKEN is set"
    return
  fi
  command -v claude >/dev/null 2>&1 || {
    echo "Claude Code CLI is required for --apply; install it and rerun." >&2
    return 1
  }
  claude mcp add --transport http --scope user context7 https://mcp.context7.com/mcp
  claude mcp add --transport stdio --scope user codebase_memory -- npx -y codebase-memory-mcp@0.8.1
  if [ -n "${GITHUB_PAT_TOKEN:-}" ]; then
    claude mcp add-json --scope user github \
      '{"type":"http","url":"https://api.githubcopilot.com/mcp/","headers":{"Authorization":"Bearer ${GITHUB_PAT_TOKEN}"}}'
  fi
}

if [ "$APPLY" = true ]; then
  echo "Portable Claude Code bootstrap (apply)"
else
  echo "Portable Claude Code bootstrap (dry-run)"
fi

install_settings || exit 1
link_item "$ROOT/CLAUDE.global.md" "$HOME/.claude/CLAUDE.md" || conflicts=$((conflicts + 1))
link_item "$ROOT/.claude/hooks" "$HOME/.claude/hooks" || conflicts=$((conflicts + 1))
link_item "$ROOT/.claude/agents" "$HOME/.claude/agents" || conflicts=$((conflicts + 1))
link_item "$ROOT/skills" "$HOME/.claude/skills" || conflicts=$((conflicts + 1))

if [ "$conflicts" -ne 0 ]; then
  echo "Found $conflicts conflict(s); nothing was overwritten." >&2
  exit 1
fi

install_mcp || exit 1

if [ "$APPLY" = false ]; then
  echo "Dry-run only. Install Claude Code, then rerun with --apply after resolving conflicts."
fi
