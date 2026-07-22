#!/usr/bin/env bash
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
APPLY=false
conflicts=0
LOCAL_CONFIG="$HOME/.codex/config.local.toml"
GENERATED_CONFIG="$ROOT/.codex/config.generated.toml"
GSTACK_MODE=off
action_seen=false
gstack_seen=false

find_python() {
  for candidate in "${PYTHON:-}" python3 "$HOME"/.local/share/uv/python/cpython-3.*/bin/python3; do
    if [ -n "$candidate" ] && command -v "$candidate" >/dev/null 2>&1 && \
       "$candidate" -c 'import tomllib' >/dev/null 2>&1; then
      echo "$candidate"
      return
    fi
  done
  echo "Python 3.11 or newer is required" >&2
  return 1
}

PYTHON=$(find_python)

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      if [ "$action_seen" = true ]; then
        echo "usage: scripts/bootstrap.sh [--dry-run|--apply] [--gstack=off|workflow|full]" >&2
        exit 2
      fi
      action_seen=true
      APPLY=false
      ;;
    --apply)
      if [ "$action_seen" = true ]; then
        echo "usage: scripts/bootstrap.sh [--dry-run|--apply] [--gstack=off|workflow|full]" >&2
        exit 2
      fi
      action_seen=true
      APPLY=true
      ;;
    --gstack=off|--gstack=workflow|--gstack=full)
      if [ "$gstack_seen" = true ]; then
        echo "usage: scripts/bootstrap.sh [--dry-run|--apply] [--gstack=off|workflow|full]" >&2
        exit 2
      fi
      gstack_seen=true
      GSTACK_MODE=${1#--gstack=}
      ;;
    *)
      echo "usage: scripts/bootstrap.sh [--dry-run|--apply] [--gstack=off|workflow|full]" >&2
      exit 2
      ;;
  esac
  shift
done

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

install_config() {
  target="$HOME/.codex/config.toml"
  merge_local="$LOCAL_CONFIG"
  preserve_local=false

  if [ -L "$target" ]; then
    current=$(readlink "$target")
    if [ "$current" != "$GENERATED_CONFIG" ]; then
      echo "conflict $target -> $current" >&2
      return 1
    fi
  elif [ -e "$target" ]; then
    if [ -e "$LOCAL_CONFIG" ]; then
      echo "conflict $target and $LOCAL_CONFIG both exist; merge them manually" >&2
      return 1
    fi
    merge_local="$target"
    preserve_local=true
    if [ "$APPLY" = false ]; then
      echo "would   preserve existing config at $LOCAL_CONFIG"
    fi
  fi

  if [ "$APPLY" = true ]; then
    if ! "$PYTHON" "$ROOT/scripts/sync_config.py" \
      --base "$ROOT/.codex/config.toml" \
      --local "$merge_local" \
      --output "$GENERATED_CONFIG"; then
      return 1
    fi
    if [ "$preserve_local" = true ]; then
      mv "$target" "$LOCAL_CONFIG"
      echo "local   preserved existing config at $LOCAL_CONFIG"
    fi
    if [ ! -L "$target" ]; then
      mkdir -p "$(dirname -- "$target")"
      if ! ln -s "$GENERATED_CONFIG" "$target"; then
        if [ "$preserve_local" = true ]; then
          mv "$LOCAL_CONFIG" "$target"
        fi
        return 1
      fi
      echo "linked  $target -> $GENERATED_CONFIG"
    else
      echo "ok      $target"
    fi
  else
    echo "would   merge portable base with $LOCAL_CONFIG"
    echo "would   $target -> $GENERATED_CONFIG"
  fi
}

prewarm_codebase_memory() {
  if [ "$APPLY" = false ]; then
    return
  fi
  echo "prewarm Codebase Memory"
  npx -y codebase-memory-mcp@0.8.1 </dev/null
}

if [ "$APPLY" = true ]; then
  echo "Portable Codex bootstrap (apply)"
else
  echo "Portable Codex bootstrap (dry-run)"
fi
echo "gstack mode: $GSTACK_MODE"
if [ "$APPLY" = true ]; then
  "$PYTHON" "$ROOT/scripts/prepare_gstack.py" --root "$ROOT" --mode "$GSTACK_MODE" --apply
else
  "$PYTHON" "$ROOT/scripts/prepare_gstack.py" --root "$ROOT" --mode "$GSTACK_MODE"
fi


if ! install_config; then
  echo "Config installation failed; no discovery links were changed." >&2
  exit 1
fi
if ! prewarm_codebase_memory; then
  echo "Codebase Memory prewarm failed; no discovery links were changed." >&2
  exit 1
fi

link_item "$ROOT/AGENTS.global.md" "$HOME/.codex/AGENTS.md" || conflicts=$((conflicts + 1))
link_item "$ROOT/.codex/hooks.json" "$HOME/.codex/hooks.json" || conflicts=$((conflicts + 1))
link_item "$ROOT/.codex/hooks" "$HOME/.codex/hooks" || conflicts=$((conflicts + 1))
link_item "$ROOT/.codex/agents" "$HOME/.codex/agents" || conflicts=$((conflicts + 1))
link_item "$ROOT/skills" "$HOME/.agents/skills" || conflicts=$((conflicts + 1))

for profile in "$ROOT"/profiles/*.config.toml; do
  link_item "$profile" "$HOME/.codex/$(basename -- "$profile")" || conflicts=$((conflicts + 1))
done

if [ "$conflicts" -ne 0 ]; then
  echo "Found $conflicts conflict(s); nothing was overwritten." >&2
  exit 1
fi

if [ "$APPLY" = true ]; then
  "$PYTHON" "$ROOT/scripts/install_gstack.py" --root "$ROOT" --mode "$GSTACK_MODE" --apply
else
  "$PYTHON" "$ROOT/scripts/install_gstack.py" --root "$ROOT" --mode "$GSTACK_MODE"
fi

if [ "$APPLY" = false ]; then
  echo "Dry-run only. Re-run with --apply after resolving any conflicts."
fi

if [ "${CODEX_CONFIG_UPDATE_CHECK:-1}" != "0" ]; then
  "$PYTHON" "$ROOT/scripts/gstack_updates.py" --notify --force || true
fi
