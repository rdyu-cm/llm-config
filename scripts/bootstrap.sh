#!/usr/bin/env bash
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
APPLY=false
conflicts=0

if [ "${1:-}" = "--apply" ]; then
  APPLY=true
elif [ "${1:-}" != "" ] && [ "${1:-}" != "--dry-run" ]; then
  echo "usage: scripts/bootstrap.sh [--dry-run|--apply]" >&2
  exit 2
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

echo "Portable Codex bootstrap ($([ "$APPLY" = true ] && echo apply || echo dry-run))"

link_item "$ROOT/AGENTS.global.md" "$HOME/.codex/AGENTS.md" || conflicts=$((conflicts + 1))
link_item "$ROOT/.codex/config.toml" "$HOME/.codex/config.toml" || conflicts=$((conflicts + 1))
link_item "$ROOT/.codex/hooks.json" "$HOME/.codex/hooks.json" || conflicts=$((conflicts + 1))
link_item "$ROOT/.codex/hooks" "$HOME/.codex/hooks" || conflicts=$((conflicts + 1))
link_item "$ROOT/.codex/agents" "$HOME/.codex/agents" || conflicts=$((conflicts + 1))
link_item "$ROOT/skills" "$HOME/.agents/skills" || conflicts=$((conflicts + 1))

for profile in "$ROOT"/profiles/*.config.toml; do
  link_item "$profile" "$HOME/.codex/$(basename -- "$profile")" || conflicts=$((conflicts + 1))
done

if [ "$APPLY" = false ]; then
  echo "Dry-run only. Re-run with --apply after resolving any conflicts."
fi

if [ "$conflicts" -ne 0 ]; then
  echo "Found $conflicts conflict(s); nothing was overwritten." >&2
  exit 1
fi
