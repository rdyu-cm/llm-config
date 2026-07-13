#!/usr/bin/env bash
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if [ "${1:-}" = "--apply" ]; then
  echo "Automatic replacement is intentionally disabled." >&2
  echo "Review upstream diffs, update sources.lock.toml, then reinstall audited paths with the Codex skill installer." >&2
  exit 2
elif [ "${1:-}" != "" ]; then
  echo "usage: scripts/update.sh" >&2
  exit 2
fi

python3 - "$ROOT/sources.lock.toml" <<'PY'
import subprocess
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    lock = tomllib.load(handle)

outdated = 0
for source in lock["sources"]:
    repository = source["repository"]
    pinned = source["commit"]
    try:
        output = subprocess.check_output(
            ["git", "ls-remote", repository, "HEAD"], text=True, stderr=subprocess.STDOUT
        )
        head = output.split()[0]
    except (subprocess.CalledProcessError, IndexError) as error:
        print(f"error   {source['name']}: {error}")
        outdated += 1
        continue
    status = "current" if head == pinned else "update"
    print(f"{status:7} {source['name']}: {pinned[:12]} -> {head[:12]}")
    outdated += head != pinned

raise SystemExit(1 if outdated else 0)
PY

