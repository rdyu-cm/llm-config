#!/usr/bin/env python3
"""Validate the repository-contained Claude Code configuration offline."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FABLE_AGENTS = {"planner", "implementer-deep", "reviewer-deep", "security-reviewer"}


def fail(message: str) -> None:
    raise ValueError(message)


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        fail(f"missing YAML frontmatter: {path.relative_to(ROOT)}")
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        field = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if field:
            values[field.group(1)] = field.group(2).strip().strip("\"'")
    return values


def load_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def main() -> int:
    settings = load_object(ROOT / ".claude/settings.json")
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict) or not {"SessionStart", "PreToolUse"} <= hooks.keys():
        fail("settings.json is missing required hooks")
    load_object(ROOT / ".claude/mcp.json")
    for path in sorted((ROOT / "profiles").glob("*.mcp.json")):
        load_object(path)
    if len(list((ROOT / "profiles").glob("*.mcp.json"))) != 4:
        fail("expected four Claude settings profiles")

    skill_names: set[str] = set()
    for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        metadata = parse_frontmatter(path)
        name = metadata.get("name", "")
        if not name:
            fail(f"missing skill metadata: {path.relative_to(ROOT)}")
        if name in skill_names:
            fail(f"duplicate skill name: {name}")
        skill_names.add(name)

    agents = sorted((ROOT / ".claude/agents").glob("*.md"))
    actual_fable: set[str] = set()
    for path in agents:
        metadata = parse_frontmatter(path)
        for field in ("name", "description", "model", "tools", "permissionMode"):
            if not metadata.get(field):
                fail(f"{path.relative_to(ROOT)} missing {field}")
        name = metadata["name"]
        model = metadata["model"]
        if model == "claude-fable-5":
            actual_fable.add(name)
        elif model != "claude-opus-5":
            fail(f"{name} uses unexpected model {model}")
    if actual_fable != FABLE_AGENTS:
        fail(f"Fable routing mismatch: {sorted(actual_fable)}")

    with (ROOT / "capability-bundle.toml").open("rb") as handle:
        bundle = tomllib.load(handle)
    for item in bundle.get("components", []):
        if not (ROOT / item["path"]).exists():
            fail(f"catalog path does not exist: {item['path']}")

    print(
        f"validated {len(skill_names)} personal skills, {len(agents)} agents, "
        f"3 hook handlers, and 4 profiles"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        print(f"validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
