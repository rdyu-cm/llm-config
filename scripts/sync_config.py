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


def merge(local: dict, portable: dict) -> dict:
    result = copy.deepcopy(local)
    for key, value in portable.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def render(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--local", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected_data = merge(load(args.local, required=False), load(args.base, required=True))
    if args.check:
        if load(args.output, required=False) != expected_data:
            print(f"stale   {args.output}; run scripts/bootstrap.sh --apply", file=sys.stderr)
            return 1
        print(f"ok      merged settings are current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    temporary.write_text(render(expected_data), encoding="utf-8")
    temporary.replace(args.output)
    print(f"merged  {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, TypeError, json.JSONDecodeError) as error:
        print(f"settings merge failed: {error}", file=sys.stderr)
        raise SystemExit(1)
