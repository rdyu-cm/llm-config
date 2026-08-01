#!/usr/bin/env python3
"""Merge portable Claude Code settings with a machine-local overlay."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path


def load(path: Path, *, required: bool) -> dict:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def union(local: list, portable: list) -> list:
    """Append portable entries the local list does not already contain.

    Replacing lists loses machine-local data that has no portable counterpart:
    an unrelated `hooks.SessionStart` handler, or an accumulated
    `permissions.allow` list. Both layers are kept, local first, and repeated
    runs stay idempotent because equal entries are only carried once.
    """
    result = copy.deepcopy(local)
    for value in portable:
        if value not in result:
            result.append(copy.deepcopy(value))
    return result


def merge(local: dict, portable: dict) -> dict:
    result = copy.deepcopy(local)
    for key, value in portable.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        elif isinstance(value, list) and isinstance(result.get(key), list):
            result[key] = union(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def render(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(render(data), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--local", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--carry",
        type=Path,
        help="Unmanaged settings to fold underneath the machine-local overlay before merging. "
        "The overlay wins on matching keys; the result is written back to --local.",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    overlay = load(args.local, required=False)
    if args.carry is not None and not args.check:
        carried = merge(load(args.carry, required=False), overlay)
        if carried != overlay:
            write(args.local, carried)
            print(f"carried {args.carry} into {args.local}")
        overlay = carried
    expected_data = merge(overlay, load(args.base, required=True))
    if args.check:
        if load(args.output, required=False) != expected_data:
            print(f"stale   {args.output}; run scripts/bootstrap.sh --apply", file=sys.stderr)
            return 1
        print(f"ok      merged settings are current: {args.output}")
        return 0
    write(args.output, expected_data)
    print(f"merged  {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, TypeError, json.JSONDecodeError) as error:
        print(f"settings merge failed: {error}", file=sys.stderr)
        raise SystemExit(1)
