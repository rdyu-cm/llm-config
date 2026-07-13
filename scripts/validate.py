#!/usr/bin/env python3
"""Validate the repository-contained Codex configuration without network access."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise ValueError(message)


def load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        fail(f"missing YAML frontmatter: {path.relative_to(ROOT)}")

    lines = match.group(1).splitlines()
    values: dict[str, str] = {}
    for index, line in enumerate(lines):
        field = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if field:
            value = field.group(2).strip().strip('"\'')
            if not value:
                continuation = []
                for next_line in lines[index + 1 :]:
                    if next_line.startswith((" ", "\t")):
                        continuation.append(next_line.strip())
                    else:
                        break
                value = " ".join(continuation)
            values[field.group(1)] = value
    for required in ("name", "description"):
        if not values.get(required):
            fail(f"missing {required} in {path.relative_to(ROOT)}")
    return values


def main() -> int:
    config = load_toml(ROOT / ".codex" / "config.toml")
    if config.get("sandbox_mode") != "workspace-write":
        fail("base sandbox_mode must remain workspace-write")

    for path in sorted((ROOT / "profiles").glob("*.config.toml")):
        load_toml(path)
    load_toml(ROOT / "sources.lock.toml")
    load_toml(ROOT / "plugins.lock.toml")

    with (ROOT / ".codex" / "hooks.json").open(encoding="utf-8") as handle:
        hooks = json.load(handle)
    if "hooks" not in hooks or "PreToolUse" not in hooks["hooks"]:
        fail("hooks.json is missing PreToolUse policy")

    names: dict[str, Path] = {}
    skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
    if not skills:
        fail("no skills installed")
    for path in skills:
        metadata = parse_frontmatter(path)
        name = metadata["name"]
        if name in names:
            fail(
                f"duplicate skill name {name}: {names[name].relative_to(ROOT)} and {path.relative_to(ROOT)}"
            )
        names[name] = path

    required_agent_fields = {"name", "description", "developer_instructions"}
    agents = sorted((ROOT / ".codex" / "agents").glob("*.toml"))
    for path in agents:
        data = load_toml(path)
        missing = sorted(required_agent_fields - data.keys())
        if missing:
            fail(f"{path.relative_to(ROOT)} missing fields: {', '.join(missing)}")

    print(f"validated {len(skills)} skills, {len(agents)} agents, 3 hooks, and 4 profiles")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, tomllib.TOMLDecodeError, json.JSONDecodeError) as error:
        print(f"validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
