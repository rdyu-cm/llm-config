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

def parse_gstack_openai_metadata(path: Path) -> dict[str, dict[str, str | bool]]:
    text = path.read_text(encoding="utf-8")
    match = re.fullmatch(
        r"interface:\n"
        r'  display_name: "([^"\n]+)"\n'
        r'  short_description: "([^"\n]+)"\n'
        r'  default_prompt: "([^"\n]+)"\n'
        r"policy:\n"
        r"  allow_implicit_invocation: true\n",
        text,
    )
    if not match:
        fail(f"invalid gstack Codex metadata YAML: {path.relative_to(ROOT)}")
    display_name, short_description, default_prompt = match.groups()
    return {
        "interface": {
            "display_name": display_name,
            "short_description": short_description,
            "default_prompt": default_prompt,
        },
        "policy": {"allow_implicit_invocation": True},
    }

def validate_gstack_vendor(root: Path, lock: dict) -> None:
    source = next((item for item in lock.get("sources", []) if item.get("name") == "gstack"), None)
    if source is None:
        fail("sources.lock.toml is missing gstack")
    vendor = root / "vendor" / "gstack"
    required = ("LICENSE", "setup", "package.json", "hosts/codex.ts", "bin/gstack-global-discover.ts")
    for relative in required:
        if not (vendor / relative).is_file():
            fail(f"vendor/gstack is missing {relative}")
    if (vendor / ".git").exists():
        fail("vendor/gstack must not contain nested Git metadata")
    license_text = (vendor / "LICENSE").read_text(encoding="utf-8")
    if "MIT License" not in license_text or "Copyright (c) 2026 Garry Tan" not in license_text:
        fail("vendor/gstack/LICENSE is not the expected upstream MIT license")
    metadata = load_toml(root / "vendor" / "gstack-source.toml")
    if metadata.get("repository") != source.get("repository"):
        fail("gstack repository metadata does not match sources.lock.toml")
    if metadata.get("commit") != source.get("commit"):
        fail("gstack commit metadata does not match sources.lock.toml")


def validate_gstack_catalog(root: Path) -> int:
    catalog = load_toml(root / "gstack-capabilities.toml")
    profiles = catalog.get("profiles")
    if not isinstance(profiles, dict):
        fail("gstack-capabilities.toml is missing profiles")

    lists: dict[str, list[str]] = {}
    for profile in ("workflow", "full"):
        skills = profiles.get(profile, {}).get("skills")
        if not isinstance(skills, list) or not all(isinstance(name, str) for name in skills):
            fail(f"gstack {profile} profile must contain a skills list")
        if len(skills) != len(set(skills)):
            fail(f"gstack {profile} profile contains duplicate skill names")
        lists[profile] = skills

    for profile, skills in lists.items():
        if "gstack-upgrade" in skills:
            fail(f"gstack-upgrade must not appear in the {profile} profile")


    full = set(lists["full"])
    generated = {
        path.name
        for path in (root / "generated" / "gstack-codex").glob("gstack-*")
        if path.is_dir()
    }
    expected_generated = full | {"gstack-upgrade"}
    missing_generated = sorted(expected_generated - generated)
    if missing_generated:
        fail(f"missing generated gstack skill: {', '.join(missing_generated)}")
    unlisted = sorted(generated - expected_generated)
    if unlisted:
        fail(f"generated gstack skills missing from full profile: {', '.join(unlisted)}")
    for name in sorted(generated):
        path = root / "generated" / "gstack-codex" / name / "SKILL.md"
        if not path.is_file():
            fail(f"missing generated gstack skill: {name}")
        metadata = parse_frontmatter(path)
        if metadata["name"] != name:
            fail(f"generated gstack skill name does not match catalog: {name}")

    sidecars = sorted((root / "generated" / "gstack-codex").glob("gstack-*/agents/openai.yaml"))
    sidecar_names = {path.parents[1].name for path in sidecars}
    missing_sidecars = sorted(generated - sidecar_names)
    if missing_sidecars:
        fail(f"generated gstack skills missing Codex metadata: {', '.join(missing_sidecars)}")
    for path in sidecars:
        name = path.parents[1].name
        interface = parse_gstack_openai_metadata(path)["interface"]
        if interface["display_name"] != name:
            fail(f"gstack Codex metadata display name does not match: {name}")
        short_description = interface["short_description"]
        if not 25 <= len(short_description) <= 64:
            fail(f"gstack Codex metadata description length is invalid: {name}")
        if f"${name}" not in interface["default_prompt"]:
            fail(f"gstack Codex metadata prompt does not invoke: {name}")



    missing = sorted(set(lists["workflow"]) - full)
    if missing:
        fail(f"gstack workflow skills missing from full profile: {', '.join(missing)}")
    for name in lists["full"]:
        path = root / "generated" / "gstack-codex" / name / "SKILL.md"
        if not path.is_file():
            fail(f"missing generated gstack skill: {name}")
        metadata = parse_frontmatter(path)
        if metadata["name"] != name:
            fail(f"generated gstack skill name does not match catalog: {name}")
    return len(lists["full"])


def main() -> int:
    config = load_toml(ROOT / ".codex" / "config.toml")
    if config.get("sandbox_mode") != "workspace-write":
        fail("base sandbox_mode must remain workspace-write")

    for path in sorted((ROOT / "profiles").glob("*.config.toml")):
        load_toml(path)
    sources = load_toml(ROOT / "sources.lock.toml")
    validate_gstack_vendor(ROOT, sources)
    gstack_skills = validate_gstack_catalog(ROOT)
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
        registration = config.get("agents", {}).get(data["name"])
        if not isinstance(registration, dict):
            fail(f"{data['name']} is not registered under [agents.{data['name']}]")
        expected_path = f"agents/{path.name}"
        if registration.get("config_file") != expected_path:
            fail(f"{data['name']} config_file must be {expected_path}")
        if registration.get("description") != data["description"]:
            fail(f"{data['name']} registration description does not match its agent file")

    print(
        f"validated {len(skills)} personal skills, {gstack_skills} generated gstack skills, "
        f"{len(agents)} agents, 3 hooks, and 4 profiles"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, tomllib.TOMLDecodeError, json.JSONDecodeError) as error:
        print(f"validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
