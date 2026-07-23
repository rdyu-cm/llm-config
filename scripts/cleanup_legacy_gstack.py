#!/usr/bin/env python3
"""Remove links recorded by the retired gstack installer without touching user paths."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


STATE_RELATIVE = Path(".codex/gstack-managed.json")


def _invalid(detail: str) -> ValueError:
    return ValueError(f"invalid legacy managed state: {detail}")


def _inside_home(home: Path, target: Path) -> bool:
    if not target.is_absolute():
        return False
    normalized_home = Path(os.path.abspath(home))
    normalized_target = Path(os.path.abspath(target))
    try:
        normalized_target.relative_to(normalized_home)
    except ValueError:
        return False
    return True


def cleanup(home: Path, apply: bool) -> list[str]:
    state = home / STATE_RELATIVE
    if not os.path.lexists(state):
        return []
    if state.is_symlink() or not state.is_file():
        raise _invalid(f"{state} must be a regular file")

    try:
        payload = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise _invalid(str(error)) from error
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise _invalid("expected a version-1 object")
    links = payload.get("links")
    if not isinstance(links, dict):
        raise _invalid("links must be an object")

    recorded: list[tuple[Path, str]] = []
    for target_text, source_text in links.items():
        if not isinstance(target_text, str) or not isinstance(source_text, str):
            raise _invalid("link paths must be strings")
        target = Path(target_text)
        if not _inside_home(home, target):
            raise ValueError(f"legacy cleanup target outside home: {target}")
        recorded.append((target, source_text))

    for target, source_text in recorded:
        if not os.path.lexists(target):
            continue
        if not target.is_symlink() or os.readlink(target) != source_text:
            raise ValueError(f"legacy cleanup conflict: {target}")

    messages: list[str] = []
    for target, _ in recorded:
        if not os.path.lexists(target):
            continue
        if apply:
            target.unlink()
            messages.append(f"removed {target}")
        else:
            messages.append(f"would   remove {target}")

    if apply:
        state.unlink()
        messages.append(f"removed {state}")
    else:
        messages.append(f"would   remove {state}")
    return messages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        messages = cleanup(args.home, args.apply)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
