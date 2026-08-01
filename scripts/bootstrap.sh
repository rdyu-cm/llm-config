#!/usr/bin/env bash
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
APPLY=false
ADOPT=false
TARGETS=""
action_seen=false
conflicts=0
adoptions=0

usage() {
  echo "usage: scripts/bootstrap.sh [--dry-run|--apply] [--target codex|claude|both] [--adopt]" >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      [ "$action_seen" = false ] || usage
      action_seen=true
      APPLY=false
      ;;
    --apply)
      [ "$action_seen" = false ] || usage
      action_seen=true
      APPLY=true
      ;;
    --adopt) ADOPT=true ;;
    --target)
      shift
      [ "$#" -gt 0 ] || usage
      case "$1" in
        codex) TARGETS="codex" ;;
        claude) TARGETS="claude" ;;
        both) TARGETS="codex claude" ;;
        *) usage ;;
      esac
      ;;
    *) usage ;;
  esac
  shift
done

find_python() {
  # tomllib landed in 3.11 and the validator imports it, so a bare `python3`
  # check passes on the 3.9 interpreters that ship with several long-term-support
  # distributions and then fails later with an unrelated import error.
  found=false
  for candidate in "${PYTHON:-}" python3 python3.13 python3.12 python3.11; do
    [ -n "$candidate" ] || continue
    command -v "$candidate" >/dev/null 2>&1 || continue
    found=true
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      echo "$candidate"
      return 0
    fi
  done
  if [ "$found" = true ]; then
    echo "Python 3.11 or newer is required; found $(python3 --version 2>&1)" >&2
  else
    echo "Python 3.11 or newer is required; no python3 interpreter was found" >&2
  fi
  return 1
}

PYTHON=$(find_python)

# Infer the target from the CLIs on PATH when none was requested, and say what
# was inferred. A machine that grows a second CLI later must not silently change
# what an unchanged command installs.
if [ -z "$TARGETS" ]; then
  command -v codex >/dev/null 2>&1 && TARGETS="codex"
  command -v claude >/dev/null 2>&1 && TARGETS="${TARGETS:+$TARGETS }claude"
  if [ -z "$TARGETS" ]; then
    echo "No Codex or Claude Code CLI found on PATH; install one, or pass --target explicitly." >&2
    exit 1
  fi
  echo "target  inferred from PATH:$(printf ' %s' $TARGETS)"
fi

# --- provider descriptors ---------------------------------------------------
# The two providers disagree on every install detail: home directory, config
# format, overlay name, where skills go, and how MCP servers are registered.
# Each accessor answers one question for the provider in TARGET.

provider_cli() { [ "$TARGET" = codex ] && echo codex || echo claude; }
provider_label() { [ "$TARGET" = codex ] && echo Codex || echo "Claude Code"; }
provider_home() { [ "$TARGET" = codex ] && echo "$HOME/.codex" || echo "$HOME/.claude"; }
provider_base() {
  [ "$TARGET" = codex ] && echo "$ROOT/.codex/config.toml" || echo "$ROOT/.claude/settings.json"
}
provider_config() {
  [ "$TARGET" = codex ] && echo "$(provider_home)/config.toml" || echo "$(provider_home)/settings.json"
}
provider_overlay() {
  [ "$TARGET" = codex ] && echo "$(provider_home)/config.local.toml" \
    || echo "$(provider_home)/settings.local.json"
}
provider_generated() {
  [ "$TARGET" = codex ] && echo "$ROOT/.codex/config.generated.toml" \
    || echo "$ROOT/.claude/settings.generated.json"
}
provider_instructions() {
  [ "$TARGET" = codex ] && echo "$ROOT/AGENTS.global.md:$(provider_home)/AGENTS.md" \
    || echo "$ROOT/CLAUDE.global.md:$(provider_home)/CLAUDE.md"
}
# Codex publishes skills to a shared directory outside its own home.
provider_skills() {
  [ "$TARGET" = codex ] && echo "$HOME/.agents/skills" || echo "$(provider_home)/skills"
}
provider_agents() {
  [ "$TARGET" = codex ] && echo "$ROOT/.codex/agents" || echo "$ROOT/.claude/agents"
}
provider_hooks() {
  [ "$TARGET" = codex ] && echo "$ROOT/.codex/hooks" || echo "$ROOT/.claude/hooks"
}

# --- linking ----------------------------------------------------------------

# A link that points into a predecessor checkout of this same configuration is
# adoptable: repointing it is a migration, not an overwrite of someone else's
# work. Anything else stays a conflict.
is_predecessor() {
  case "$1" in
    */codex-config/*|*/claude-config/*|*/codex-config|*/claude-config) return 0 ;;
    *) return 1 ;;
  esac
}

link_item() {
  source_path=$1
  target_path=$2
  if [ -L "$target_path" ]; then
    current=$(readlink "$target_path")
    if [ "$current" = "$source_path" ]; then
      echo "ok      $target_path"
      return 0
    fi
    if is_predecessor "$current"; then
      adoptions=$((adoptions + 1))
      if [ "$ADOPT" != true ]; then
        echo "adoptable $target_path -> $current" >&2
        return 1
      fi
      if [ "$APPLY" = true ]; then
        rm -f "$target_path"
        ln -s "$source_path" "$target_path"
        echo "adopted $target_path -> $source_path"
      else
        echo "would   adopt $target_path (was $current)"
      fi
      return 0
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

link_children() {
  # Both providers discover skills and agents by name inside a shared directory
  # that other tools also install into. Linking the directory itself would make
  # any pre-existing entry an unresolvable conflict, so each entry is linked
  # individually and unrelated neighbours are left alone.
  source_dir=$1
  target_dir=$2
  status=0
  # An older layout linked the whole directory. Descending into such a link
  # would write entries through it and into the repository it points at, so the
  # link is resolved first and never followed.
  if [ -L "$target_dir" ]; then
    current=$(readlink "$target_dir")
    if [ "$current" = "$source_dir" ] || is_predecessor "$current"; then
      adoptions=$((adoptions + 1))
      if [ "$ADOPT" != true ]; then
        echo "adoptable $target_dir -> $current (whole-directory link)" >&2
        return 1
      fi
      if [ "$APPLY" = true ]; then
        rm -f "$target_dir"
        echo "adopted $target_dir (was a link to $current)"
      else
        echo "would   adopt $target_dir (was a link to $current)"
        return 0
      fi
    else
      echo "conflict $target_dir -> $current; move or merge it manually" >&2
      return 1
    fi
  fi
  if [ "$APPLY" = true ]; then
    mkdir -p "$target_dir"
  fi
  for source_path in "$source_dir"/*; do
    [ -e "$source_path" ] || continue
    link_item "$source_path" "$target_dir/$(basename -- "$source_path")" || status=1
  done
  return "$status"
}

install_config() {
  target=$(provider_config)
  overlay=$(provider_overlay)
  generated=$(provider_generated)
  # Each provider owns its active config and writes its own machine-local
  # overlay, so neither file existing is a conflict. Anything in the active file
  # that this repository did not generate is unmanaged and gets folded into the
  # overlay instead of being discarded. A byte-identical match against the last
  # generated file is how a previous apply is recognized, which keeps portable
  # values from being baked into the overlay on every rerun.
  carry=""
  if [ -e "$target" ]; then
    if [ -e "$generated" ] && cmp -s "$target" "$generated"; then
      echo "ok      $target was generated by this repository"
    else
      carry="$target"
      echo "would   fold unmanaged $target into $overlay"
    fi
  fi
  if [ "$APPLY" = true ]; then
    if [ -n "$carry" ]; then
      "$PYTHON" "$ROOT/scripts/sync_config.py" \
        --base "$(provider_base)" --local "$overlay" --carry "$carry" --output "$generated"
    else
      "$PYTHON" "$ROOT/scripts/sync_config.py" \
        --base "$(provider_base)" --local "$overlay" --output "$generated"
    fi
    mkdir -p "$(dirname -- "$target")"
    cp "$generated" "$target.tmp"
    mv "$target.tmp" "$target"
    echo "installed $target"
  else
    echo "would   merge portable config with $overlay"
    echo "would   install merged config at $target"
  fi
}

install_mcp() {
  # Codex declares MCP servers inside config.toml, so installing the config
  # already registered them. Claude Code registers them through its CLI.
  if [ "$TARGET" = codex ]; then
    echo "ok      MCP servers are declared in config.toml"
    return 0
  fi
  if [ "$APPLY" = false ]; then
    echo "would   add user MCP servers: context7, codebase_memory"
    echo "would   add user MCP server github only when GITHUB_PAT_TOKEN is set"
    return 0
  fi
  command -v claude >/dev/null 2>&1 || {
    echo "Claude Code CLI is required to register MCP servers; install it and rerun." >&2
    return 1
  }
  claude mcp add --transport http --scope user context7 https://mcp.context7.com/mcp
  claude mcp add --transport stdio --scope user codebase_memory -- npx -y codebase-memory-mcp@0.8.1
  if [ -n "${GITHUB_PAT_TOKEN:-}" ]; then
    claude mcp add-json --scope user github \
      '{"type":"http","url":"https://api.githubcopilot.com/mcp/","headers":{"Authorization":"Bearer ${GITHUB_PAT_TOKEN}"}}'
  fi
}

install_target() {
  echo
  if [ "$APPLY" = true ]; then
    echo "== $(provider_label) (apply)"
  else
    echo "== $(provider_label) (dry-run)"
  fi

  if [ "$APPLY" = true ] && ! command -v "$(provider_cli)" >/dev/null 2>&1; then
    echo "$(provider_label) CLI is required for --apply; install it or drop it from --target." >&2
    return 1
  fi

  install_config || return 1

  instructions=$(provider_instructions)
  link_item "${instructions%%:*}" "${instructions##*:}" || conflicts=$((conflicts + 1))
  link_item "$(provider_hooks)" "$(provider_home)/hooks" || conflicts=$((conflicts + 1))
  link_children "$(provider_agents)" "$(provider_home)/agents" || conflicts=$((conflicts + 1))
  link_children "$ROOT/skills" "$(provider_skills)" || conflicts=$((conflicts + 1))

  if [ "$TARGET" = codex ]; then
    link_item "$ROOT/.codex/hooks.json" "$(provider_home)/hooks.json" || conflicts=$((conflicts + 1))
    for profile in "$ROOT"/profiles/*.config.toml; do
      [ -e "$profile" ] || continue
      link_item "$profile" "$(provider_home)/$(basename -- "$profile")" || conflicts=$((conflicts + 1))
    done
  fi

  install_mcp || return 1
}

if [ "$APPLY" = true ]; then
  echo "Portable agent configuration bootstrap (apply)"
else
  echo "Portable agent configuration bootstrap (dry-run)"
fi

for TARGET in $TARGETS; do
  install_target || exit 1
done

echo
if [ "$conflicts" -ne 0 ]; then
  echo "Found $conflicts conflict(s); nothing was overwritten." >&2
  if [ "$adoptions" -ne 0 ] && [ "$ADOPT" != true ]; then
    echo "$adoptions of them point into a predecessor checkout of this configuration." >&2
    echo "Rerun with --adopt to repoint those and leave the rest untouched." >&2
  fi
  exit 1
fi

if [ "$APPLY" = false ]; then
  echo "Dry-run only. Rerun with --apply after resolving conflicts."
fi
