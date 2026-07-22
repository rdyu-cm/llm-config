#!/usr/bin/env python3
"""Prepare an explicit, reviewable gstack vendor update."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
import uuid
from pathlib import Path, PurePosixPath


REPOSITORY = "https://github.com/garrytan/gstack"
REQUIRED_VENDOR_FILES = ("LICENSE", "setup", "package.json", "hosts/codex.ts")
UPDATE_PATHS = (
    "vendor/gstack",
    "vendor/gstack-source.toml",
    "generated/gstack-codex",
    "generated/gstack-codex-workflow",
    "sources.lock.toml",
)
RUNTIME_PATH_VARIABLES = ("GSTACK_BROWSE", "GSTACK_DESIGN", "GSTACK_MAKE_PDF")


def validate_candidate(candidate: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", candidate) is None:
        raise ValueError("candidate must be 40 hexadecimal lowercase characters")


def _archive_parts(member: tarfile.TarInfo) -> tuple[str, ...]:
    path = PurePosixPath(member.name)
    if "\\" in member.name or re.match(r"^[A-Za-z]:", member.name):
        raise ValueError(f"unsafe archive path: {member.name}")
    parts = path.parts
    if path.is_absolute() or not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"unsafe archive path: {member.name}")
    return parts


def extract_archive(archive: Path, destination: Path) -> Path:
    """Safely extract a regular-file-only archive and return its sole root."""
    with tarfile.open(archive, "r:gz") as handle:
        members = handle.getmembers()
        if not members:
            raise ValueError("archive must contain exactly one root")

        roots: set[str] = set()
        seen: set[tuple[str, ...]] = set()
        checked: list[tuple[tarfile.TarInfo, tuple[str, ...]]] = []
        for member in members:
            parts = _archive_parts(member)
            roots.add(parts[0])
            if parts in seen:
                raise ValueError(f"duplicate archive path: {member.name}")
            seen.add(parts)
            if member.issym() or member.islnk():
                raise ValueError(f"archive link is not allowed: {member.name}")
            if member.ischr() or member.isblk() or member.isfifo():
                raise ValueError(f"archive device is not allowed: {member.name}")
            if not member.isdir() and not member.isfile():
                raise ValueError(f"unsupported archive member: {member.name}")
            if len(parts) == 1 and not member.isdir():
                raise ValueError("archive root must be a directory")
            checked.append((member, parts))

        if len(roots) != 1:
            raise ValueError("archive must contain exactly one root")

        destination.mkdir(parents=True, exist_ok=False)
        directories: list[tuple[Path, int]] = []
        for member, parts in checked:
            output = destination.joinpath(*parts)
            if member.isdir():
                output.mkdir(parents=True, exist_ok=True)
                directories.append((output, member.mode))
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            source = handle.extractfile(member)
            if source is None:
                raise ValueError(f"unable to read archive member: {member.name}")
            with source, output.open("xb") as target:
                shutil.copyfileobj(source, target)
            output.chmod(member.mode & 0o777)

        for directory, mode in reversed(directories):
            directory.chmod(mode & 0o777)
    return destination / roots.pop()


def validate_vendor_tree(vendor: Path) -> None:
    for relative in REQUIRED_VENDOR_FILES:
        path = vendor / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"candidate vendor tree is missing {relative}")
    if (vendor / ".git").exists() or (vendor / ".git").is_symlink():
        raise ValueError("candidate vendor tree contains nested Git metadata")


def _load_catalog(root: Path) -> dict:
    with (root / "gstack-capabilities.toml").open("rb") as handle:
        return tomllib.load(handle)


def _catalog_skill_names(root: Path) -> set[str]:
    catalog = _load_catalog(root)
    skills = catalog.get("profiles", {}).get("full", {}).get("skills")
    if not isinstance(skills, list) or not all(isinstance(name, str) for name in skills):
        raise ValueError("gstack full profile must contain a skills list")
    if len(skills) != len(set(skills)):
        raise ValueError("gstack full profile contains duplicate skill names")
    if "gstack-upgrade" in skills:
        raise ValueError("gstack-upgrade must remain outside the full profile")
    return set(skills) | {"gstack-upgrade"}


def _catalog_workflow_skill_names(root: Path) -> set[str]:
    catalog = _load_catalog(root)
    skills = catalog.get("profiles", {}).get("workflow", {}).get("skills")
    if not isinstance(skills, list) or not all(isinstance(name, str) for name in skills):
        raise ValueError("gstack workflow profile must contain a skills list")
    if len(skills) != len(set(skills)):
        raise ValueError("gstack workflow profile contains duplicate skill names")
    return set(skills)


def _validate_candidate_inventory(root: Path, vendor: Path) -> None:
    actual: set[str] = set()
    for directory in vendor.iterdir():
        if directory.is_symlink() or not directory.is_dir():
            continue
        template = directory / "SKILL.md.tmpl"
        if not template.exists():
            continue
        if template.is_symlink() or not template.is_file():
            raise ValueError(f"candidate skill template is unsafe: {directory.name}")
        if re.fullmatch(r"[a-z0-9][a-z0-9-]*", directory.name) is None:
            raise ValueError(f"candidate skill directory is invalid: {directory.name}")
        actual.add(
            directory.name if directory.name == "gstack-upgrade" else f"gstack-{directory.name}"
        )

    expected = _catalog_skill_names(root)
    added = sorted(actual - expected)
    removed = sorted(expected - actual)
    if added or removed:
        details = []
        if added:
            details.append(f"added: {', '.join(added)}")
        if removed:
            details.append(f"removed: {', '.join(removed)}")
        raise ValueError(
            f"candidate skill inventory changed; catalog review required ({'; '.join(details)})"
        )


def _catalog_generated_root(root: Path, profile: str) -> Path:
    catalog = _load_catalog(root)
    relative = catalog.get("profiles", {}).get(profile, {}).get("generated_root")
    expected = {
        "full": "generated/gstack-codex",
        "workflow": "generated/gstack-codex-workflow",
    }.get(profile)
    if relative != expected:
        raise ValueError(f"gstack {profile} profile must use generated root {expected}")
    return root / relative


def _validate_generated_tree(root: Path, generated: Path, profile: str = "full") -> None:
    expected = (
        _catalog_skill_names(root)
        if profile == "full"
        else _catalog_workflow_skill_names(root)
    )
    actual = {path.name for path in generated.iterdir() if path.is_dir() and not path.is_symlink()}
    if actual != expected:
        missing = ", ".join(sorted(expected - actual))
        extra = ", ".join(sorted(actual - expected))
        raise ValueError(f"generated gstack catalog mismatch (missing: {missing or '-'}; extra: {extra or '-'})")

    for path in generated.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"generated gstack output contains a symlink: {path.name}")
    for name in sorted(expected):
        skill = generated / name / "SKILL.md"
        metadata = generated / name / "agents/openai.yaml"
        if not skill.is_file() or not metadata.is_file():
            raise ValueError(f"generated gstack skill is incomplete: {name}")
        frontmatter = skill.read_text(encoding="utf-8")
        if re.match(rf"\A---\n(?:(?!\n---\n).)*^name:\s*{re.escape(name)}\s*$", frontmatter, re.MULTILINE | re.DOTALL) is None:
            raise ValueError(f"generated gstack skill name does not match: {name}")
        if re.search(r"(?:~?/)?\.claude/skills", frontmatter):
            raise ValueError(f"generated gstack skill contains a Claude path: {name}")
        if "$HOME$GSTACK_" in frontmatter:
            raise ValueError(f"generated gstack skill contains a doubled home prefix: {name}")
        for variable in RUNTIME_PATH_VARIABLES:
            if re.search(rf"\$(?:\{{)?{variable}(?:\}})?", frontmatter) and re.search(
                rf"(?m)^{variable}=", frontmatter
            ) is None:
                raise ValueError(
                    f"generated gstack skill uses {variable} without initialization: {name}"
                )
        if profile == "workflow" and name == "gstack-office-hours":
            browser_setup_fallbacks = (
                "NEEDS_SETUP",
                "cd <SKILL_DIR> && ./setup",
                "bun.sh/install",
                "Run the setup script to enable it.",
                "file://",
                "--serve",
            )
            if any(fallback in frontmatter for fallback in browser_setup_fallbacks):
                raise ValueError(
                    "generated gstack skill contains a browser setup fallback: "
                    "gstack-office-hours"
                )
            for instruction in (
                "Skip browser preview and setup",
                "report the saved artifact path",
                "Report the HTML artifact path",
            ):
                if instruction not in frontmatter:
                    raise ValueError(
                        "generated gstack skill is missing its optional browser fallback: "
                        "gstack-office-hours"
                    )
        if profile == "workflow" and name == "gstack-plan-design-review":
            if any(
                fallback in frontmatter
                for fallback in ("open file://", "--serve", "$D serve")
            ):
                raise ValueError(
                    "generated gstack skill contains a system browser fallback: "
                    "gstack-plan-design-review"
                )
            for instruction in (
                "save the comparison board HTML",
                "report its artifact path",
                "continue the non-browser review flow",
                "BROWSE_READY: $B",
            ):
                if instruction not in frontmatter:
                    raise ValueError(
                        "generated gstack skill is missing its optional browser fallback: "
                        "gstack-plan-design-review"
                    )
        trusted_skill = _catalog_generated_root(root, profile) / name / "SKILL.md"
        if trusted_skill.is_file() and not trusted_skill.is_symlink():
            trusted_text = trusted_skill.read_text(encoding="utf-8")
            for initialization in ("GSTACK_ROOT=", "GSTACK_BIN="):
                if initialization in trusted_text and initialization not in frontmatter:
                    raise ValueError(
                        f"generated gstack skill is missing {initialization.rstrip('=')}: {name}"
                    )
        if re.search(r"(?<!\$)\{\{[A-Z_][A-Z0-9_]*(?::[^}\n]+)?\}\}", frontmatter):
            raise ValueError(f"generated gstack skill contains an unresolved template: {name}")
        metadata_text = metadata.read_text(encoding="utf-8")
        expected_metadata = (
            f'interface:\n  display_name: "{name}"\n'
            f'  short_description: "Use the ${name} workflow."\n'
            f'  default_prompt: "Invoke ${name} for this task."\n'
            'policy:\n  allow_implicit_invocation: true\n'
        )
        if metadata_text != expected_metadata:
            raise ValueError(f"generated gstack metadata does not match: {name}")


def write_codex_metadata(path: Path, name: str) -> None:
    if re.fullmatch(r"gstack-[a-z0-9-]+", name) is None:
        raise ValueError(f"invalid generated gstack skill name: {name}")
    _atomic_write(
        path,
        f'interface:\n  display_name: "{name}"\n'
        f'  short_description: "Use the ${name} workflow."\n'
        f'  default_prompt: "Invoke ${name} for this task."\n'
        'policy:\n  allow_implicit_invocation: true\n',
    )


def _adapt_codex_skill(source: str, name: str, *, workflow_safe: bool = False) -> str:
    match = re.fullmatch(r"---\r?\n(.*?)\r?\n---\r?\n?(.*)", source, re.DOTALL)
    if match is None:
        raise ValueError(f"candidate skill is missing frontmatter: {name}")
    frontmatter, body = match.groups()
    lines = frontmatter.splitlines()
    description_start = next(
        (index for index, line in enumerate(lines) if re.match(r"^description\s*:", line)), None
    )
    if description_start is None:
        raise ValueError(f"candidate skill is missing description: {name}")
    description_end = description_start + 1
    value = lines[description_start].split(":", 1)[1].strip()
    if value in {"|", "|-", "|+", ">", ">-", ">+"}:
        while description_end < len(lines) and (
            not lines[description_end] or lines[description_end][0].isspace()
        ):
            description_end += 1
        description_text = "\n".join(
            line[2:] if line.startswith("  ") else line
            for line in lines[description_start + 1 : description_end]
        ).strip()
    else:
        description_text = value.strip('"\'')
    discovery = re.search(
        r"(?m)^## When to invoke this skill\s*\n+(.*?)(?=^## |\Z)", body, re.DOTALL
    )
    if discovery is not None:
        routing = discovery.group(1).strip()
        suffix = " (gstack)"
        if description_text.endswith(suffix):
            description_text = description_text[: -len(suffix)]
        description_text = f"{description_text} {routing}{suffix}".strip()
        body = body[: discovery.start()] + body[discovery.end() :]
    description = "description: |\n" + "\n".join(f"  {line}" for line in description_text.splitlines())
    preamble = "## Preamble (run first)\n\n```bash\n"
    initialization = (
        "_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)\n"
        'GSTACK_ROOT="$HOME/.codex/skills/gstack"\n'
        '[ -n "$_ROOT" ] && [ -d "$_ROOT/.agents/skills/gstack" ] && '
        'GSTACK_ROOT="$_ROOT/.agents/skills/gstack"\n'
        'GSTACK_BIN="$GSTACK_ROOT/bin"\n'
        'GSTACK_BROWSE="$GSTACK_ROOT/browse/dist"\n'
        'GSTACK_DESIGN="$GSTACK_ROOT/design/dist"\n'
    )
    if "$GSTACK_MAKE_PDF" in body:
        initialization += 'GSTACK_MAKE_PDF="$GSTACK_ROOT/make-pdf"\n'
    if preamble in body and "GSTACK_ROOT=" not in body:
        body = body.replace(preamble, preamble + initialization, 1)
    adapted = f"---\nname: {name}\n{description}\n---\n{body}"
    for old, new in (
        ("$HOME$GSTACK_BROWSE", "$GSTACK_BROWSE"),
        ("$HOME$GSTACK_DESIGN", "$GSTACK_DESIGN"),
        ("$HOME$GSTACK_MAKE_PDF", "$GSTACK_MAKE_PDF"),
        ("~/.claude/skills/gstack", "$GSTACK_ROOT"),
        (".claude/skills/gstack", ".agents/skills/gstack"),
        (".claude/skills/review", ".agents/skills/gstack/review"),
        (".claude/skills", ".agents/skills"),
    ):
        adapted = adapted.replace(old, new)
    if workflow_safe:
        return _apply_workflow_safe_fallbacks(adapted, name)
    return adapted


def _apply_workflow_safe_fallbacks(adapted: str, name: str) -> str:
    """Remove launch/setup flows from skills shared by the workflow profile."""
    adapted = adapted.replace(
        'like /qa for "does this work?" or /investigate for bugs?',
        "like running the project's tests for \"does this work?\" or /investigate for bugs?",
    )
    adapted = adapted.replace(
        "\"There's code here — `/qa` to see it work, or `/investigate` if something's off.\"",
        "\"There's code here — run its automated tests, or `/investigate` if something's off.\"",
    )
    adapted = adapted.replace(
        '"Pick one: `/spec`, `/investigate`, or `/qa`."',
        '"Pick one: `/spec`, `/investigate`, or `/review`."',
    )
    adapted = adapted.replace(
        "- QA/testing site behavior → invoke /qa or /qa-only",
        "- Verification → run existing automated tests and inspect logs, command output, and artifacts",
    )
    adapted = adapted.replace(
        "operational skills like `/ship`, `/qa`, `/review`",
        "operational skills like `/ship` and `/review`",
    )
    adapted = re.sub(
        r"write a test plan artifact to the project directory so `(?:/qa|project tests)` "
        r"and `(?:/qa-only|automated verification)` can consume it as primary test input:",
        "write a test plan artifact to the project directory for existing automated "
        "verification:",
        adapted,
    )
    adapted = re.sub(
        r"This file is consumed by `(?:/qa|project tests)` and "
        r"`(?:/qa-only|automated verification)` as primary test input\.",
        "Use this file as primary input for existing automated verification.",
        adapted,
    )
    adapted = re.sub(
        r"write a test plan artifact so `(?:/qa|project tests)` and "
        r"`(?:/qa-only|automated verification)` can consume it:",
        "write a test plan artifact for existing automated verification:",
        adapted,
    )
    adapted = adapted.replace(" /qa(8)", " tests(8)")
    adapted = adapted.replace(" project tests(8)", " tests(8)")
    adapted = adapted.replace(
        ", writes to the plan file, and `open` for generated artifacts.",
        ", and writes to the plan file.",
    )
    adapted = re.sub(
        r'(?m)^If `LAKE_INTRO` is `no`: say (?P<message>".*") Offer to open:\n\n'
        r'```bash\nopen (?P<url>https://\S+)\ntouch (?P<marker>\S+)\n```\n\n'
        r'Only run `open` if yes\. Always run `touch`\.',
        lambda match: (
            f"If `LAKE_INTRO` is `no`: say {match.group('message')}. "
            "Report the URL above without launching it, then run:\n\n"
            f"```bash\ntouch {match.group('marker')}\n```"
        ),
        adapted,
    )
    if name == "gstack-office-hours":
        adapted = re.sub(
            r"(?ms)^## (?:SETUP \(run this check BEFORE any browse command\)|"
            r"OPTIONAL BROWSER RUNTIME \(check before preview\))\n.*?(?=^# YC Office Hours)",
            "## Browser-free workflow\n\n"
            "Skip browser preview and setup. Do not install or recommend browser tooling. "
            "Continue the text/artifact workflow and report the saved artifact path whenever "
            "a preview file is produced.\n\n",
            adapted,
            count=1,
        )
        adapted = re.sub(
            r"(?ms)^\*\*Step 4: Show variants inline, then open comparison board\*\*\n.*?"
            r"(?=^\*\*Step 6: Save approved choice\*\*)",
            "**Step 4: Save the comparison artifact**\n\n"
            "Show each variant inline with the Read tool, then write the comparison HTML:\n\n"
            "```bash\n"
            '$D compare --images "$_DESIGN_DIR/variant-A.png,$_DESIGN_DIR/variant-B.png,'
            '$_DESIGN_DIR/variant-C.png" --output "$_DESIGN_DIR/design-board.html"\n'
            "```\n\n"
            "Report the saved comparison artifact path. Do not start a server or launch a "
            "browser.\n\n"
            "**Step 5: Continue in text**\n\n"
            "Skip the browser-only comparison loop. Use the inline variants and "
            "AskUserQuestion for any necessary choice, then continue the text workflow.\n\n",
            adapted,
            count=1,
        )
        adapted = re.sub(
            r"(?ms)^\*\*Step 3: Render and capture\*\*\n.*?"
            r"(?=^\*\*Step 6: Outside design voices\*\*)",
            "**Step 3: Keep the HTML artifact**\n\n"
            "Do not launch a preview or capture a screenshot. Report the HTML artifact path in "
            "`SKETCH_FILE`, skip browser-only iteration, and continue the text workflow.\n\n"
            "**Step 4: Continue without preview**\n\n"
            "Record any textual feedback directly in the HTML or design doc.\n\n"
            "**Step 5: Include in design doc**\n\n"
            "Reference the saved HTML artifact in the design doc's Recommended Approach section.\n\n",
            adapted,
            count=1,
        )
        adapted = adapted.replace(
            '- If yes: run `open https://ycombinator.com/apply?ref=gstack` and say: '
            '"Bring this design doc to your YC interview. It\'s better than most pitch decks."',
            '- If yes: report `https://ycombinator.com/apply?ref=gstack` and say: '
            '"Bring this design doc to your YC interview. It\'s better than most pitch decks."',
            1,
        )
        adapted = adapted.replace(
            "second person, referencing specific things they said across sessions. Then open it:\n"
            "```bash\n"
            'eval "$($GSTACK_ROOT/bin/gstack-paths)"\n'
            'open "$GSTACK_STATE_ROOT/builder-journey.md"\n'
            "```",
            "second person, referencing specific things they said across sessions. Then report "
            "its artifact path:\n"
            "```bash\n"
            'eval "$($GSTACK_ROOT/bin/gstack-paths)"\n'
            'printf \'%s\\n\' "$GSTACK_STATE_ROOT/builder-journey.md"\n'
            "```",
            1,
        )
        adapted = adapted.replace(
            "Auto-generate updated `~/.gstack/builder-journey.md` with narrative arc. Open it.",
            "Auto-generate updated `~/.gstack/builder-journey.md` with narrative arc and report "
            "its artifact path.",
            1,
        )
        adapted = re.sub(
            r"(?ms)^3\. Use AskUserQuestion to offer opening the resources:\n.*?"
            r"(?=^### Next-skill recommendations)",
            "3. Present the selected resource URLs directly in the response. Do not launch them. "
            "Then continue to next-skill recommendations.\n\n",
            adapted,
            count=1,
        )
    elif name == "gstack-plan-design-review":
        adapted = adapted.replace(
            "- `open` (fallback for viewing boards when `$B` is not available)\n",
            "",
            1,
        )
        adapted = adapted.replace(
            '  echo "BROWSE_NOT_AVAILABLE (will use \'open\' to view comparison boards)"',
            '  echo "BROWSE_NOT_AVAILABLE (comparison board will remain a saved artifact)"',
            1,
        )
        adapted = adapted.replace(
            "If `BROWSE_NOT_AVAILABLE`: use `open file://...` instead of `$B goto` to open\n"
            "comparison boards. The user just needs to see the HTML file in any browser.",
            "If `BROWSE_NOT_AVAILABLE`: save the comparison board HTML, report its artifact path,\n"
            "and continue the non-browser review flow. Do not invoke a system browser.",
            1,
        )
        adapted = adapted.replace(
            '- `$D compare --images "a.png,b.png,c.png" --output /path/board.html --serve` — '
            "comparison board + HTTP server\n"
            "- `$D serve --html /path/board.html` — serve comparison board and collect feedback "
            "via HTTP",
            '- `$D compare --images "a.png,b.png,c.png" --output /path/board.html` — write the '
            "comparison board HTML artifact",
            1,
        )
        adapted = re.sub(
            r"(?ms)^\*\*Do NOT show variants inline via Read tool and ask for preferences\.\*\*"
            r".*?(?=^## The 0-10 Rating Method)",
            "**Artifact-only comparison**\n\n"
            "If `DESIGN_READY`, show generated variants inline with the Read tool and write the "
            "comparison artifact:\n\n"
            "```bash\n"
            '$D compare --images "$_DESIGN_DIR/variant-A.png,$_DESIGN_DIR/variant-B.png,'
            '$_DESIGN_DIR/variant-C.png" --output "$_DESIGN_DIR/design-board.html"\n'
            "```\n\n"
            "Report the saved comparison artifact path. Do not start a server or launch a browser. "
            "Skip the browser-only feedback loop and continue the text review, using "
            "AskUserQuestion for genuine design choices.\n\n"
            "If `DESIGN_NOT_AVAILABLE`, skip visual generation and setup guidance. Continue the "
            "text review and report any artifacts already produced.\n\n",
            adapted,
            count=1,
        )
        adapted = adapted.replace(
            "* **NEVER use AskUserQuestion to ask which variant the user prefers.** Always create "
            "a comparison board first (`$D compare --serve`) and open it in the browser. The board "
            "has rating controls, comments, remix/regenerate buttons, and structured feedback "
            "output. Use AskUserQuestion ONLY to notify the user the board is open and wait for "
            'them to finish — not to present variants inline and ask "which do you prefer?" That '
            "is a degraded experience.",
            "* Use AskUserQuestion for any necessary variant preference in the text workflow. "
            "Do not serve or launch the comparison artifact.",
            1,
        )
    if name == "gstack-ship":
        adapted = re.sub(
            r"(?ms)^## Step 8\.1: Plan Verification\n.*?(?=^## Prior Learnings)",
            "## Step 8.1: Plan Verification\n\n"
            "Verify the plan's testing and verification steps without browser tooling.\n\n"
            "1. Find the plan's verification section. If none exists, record that verification "
            "was skipped.\n"
            "2. Extract existing test, lint, type-check, build, and validation commands plus any "
            "artifact paths named by the plan.\n"
            "3. Run the existing automated verification commands in the repository. Do not "
            "launch a browser, probe or start a development server, or request screenshots.\n"
            "4. Inspect exit status, logs, command output, and generated artifacts. Record each "
            "plan item as PASS, FAIL, or SKIPPED with concrete non-browser evidence.\n"
            "5. If any item fails, use AskUserQuestion to offer fixing the failure before ship "
            "or shipping with the known issue. Cite the failing command and relevant log or "
            "artifact path.\n\n"
            "Add a `## Verification Results` section to the PR body with the commands run, "
            "PASS/FAIL/SKIPPED counts, and evidence paths.\n\n",
            adapted,
            count=1,
        )

    # Browser-only QA skills are absent from the workflow profile. Remove any exact
    # tokens left in less-common upstream prose after the targeted guidance rewrites.
    adapted = re.sub(
        r"(?<![A-Za-z0-9_-])/qa-only\b", "automated verification", adapted
    )
    adapted = re.sub(
        r"(?<![A-Za-z0-9_-])/qa\b", "project tests", adapted
    )
    return adapted




def _suppress_trusted_codex_sections(
    candidate: str, trusted_source: str, trusted_generated: str
) -> str:
    """Remove only source sections intentionally omitted by the trusted adapter."""
    trusted_headings = re.findall(r"(?m)^## [^\n]+$", trusted_source)
    omitted_headings = [
        heading
        for heading in trusted_headings
        if re.search(rf"(?m)^{re.escape(heading)}$", trusted_generated) is None
    ]
    for heading in omitted_headings:
        candidate = re.sub(
            rf"(?ms)^{re.escape(heading)}\n.*?(?=^## |\Z)",
            "",
            candidate,
            count=1,
        )
    return candidate


def _candidate_skill_path(vendor: Path, name: str) -> Path:
    relative = name if name == "gstack-upgrade" else name.removeprefix("gstack-")
    return vendor / relative / "SKILL.md"


def generate_codex_skills(
    root: Path, staged_vendor: Path, staged_generated: Path, profile: str = "full"
) -> None:
    trusted_generated = _catalog_generated_root(root, profile)
    trusted_vendor = root / "vendor/gstack"
    names = (
        _catalog_skill_names(root)
        if profile == "full"
        else _catalog_workflow_skill_names(root)
    )
    for name in sorted(names):
        destination = staged_generated / name
        source = _candidate_skill_path(staged_vendor, name)
        trusted_source = _candidate_skill_path(trusted_vendor, name)
        fallback = trusted_generated / name
        source_matches_trusted = (
            source.is_file()
            and not source.is_symlink()
            and trusted_source.is_file()
            and not trusted_source.is_symlink()
            and source.read_bytes() == trusted_source.read_bytes()
        )
        if source_matches_trusted or not source.is_file():
            if not fallback.is_dir() or fallback.is_symlink():
                raise ValueError(f"candidate and trusted fallback are missing {name}")
            shutil.copytree(fallback, destination)
        elif not source.is_symlink():
            destination.mkdir()
            workflow_safe = profile == "workflow"
            adapted = _adapt_codex_skill(
                source.read_text(encoding="utf-8"), name, workflow_safe=workflow_safe
            )
            trusted_skill = fallback / "SKILL.md"
            if (
                trusted_source.is_file()
                and not trusted_source.is_symlink()
                and trusted_skill.is_file()
                and not trusted_skill.is_symlink()
            ):
                adapted = _suppress_trusted_codex_sections(
                    adapted,
                    _adapt_codex_skill(
                        trusted_source.read_text(encoding="utf-8"),
                        name,
                        workflow_safe=workflow_safe,
                    ),
                    trusted_skill.read_text(encoding="utf-8"),
                )
            (destination / "SKILL.md").write_text(adapted, encoding="utf-8")
        else:
            raise ValueError(f"candidate skill is unsafe: {name}")
        (destination / "agents").mkdir(exist_ok=True)
        write_codex_metadata(destination / "agents/openai.yaml", name)


def replace_directory(staged: Path, target: Path) -> None:
    backup = target.with_name(f".{target.name}.backup-{uuid.uuid4().hex}")
    had_target = target.exists()
    if target.is_symlink() or staged.is_symlink():
        raise ValueError("directory replacement does not accept symlinks")
    if had_target:
        os.replace(target, backup)
    try:
        os.replace(staged, target)
    except OSError:
        if had_target:
            os.replace(backup, target)
        raise
    if had_target:
        shutil.rmtree(backup)


def _atomic_write(path: Path, content: str) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _read_text_exact(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def update_lock_commit(path: Path, candidate: str) -> None:
    validate_candidate(candidate)
    text = _read_text_exact(path)
    table_starts = list(re.finditer(r"^\[\[sources\]\]\s*(?:#.*)?$", text, re.MULTILINE))
    matches: list[tuple[int, int, str]] = []
    for index, table in enumerate(table_starts):
        start = table.start()
        end = table_starts[index + 1].start() if index + 1 < len(table_starts) else len(text)
        block = text[start:end]
        if re.search(r'^\s*name\s*=\s*"gstack"\s*(?:#.*)?$', block, re.MULTILINE):
            matches.append((start, end, block))
    if len(matches) != 1:
        raise ValueError("sources.lock.toml must contain exactly one gstack source")

    start, end, block = matches[0]
    commit_pattern = re.compile(r'^(\s*commit\s*=\s*")[^"\n]*("[^\n]*)$', re.MULTILINE)
    commit_lines = list(commit_pattern.finditer(block))
    if len(commit_lines) != 1:
        raise ValueError("gstack source must contain exactly one commit line")
    updated = commit_pattern.sub(lambda match: f"{match.group(1)}{candidate}{match.group(2)}", block, count=1)
    _atomic_write(path, text[:start] + updated + text[end:])


def write_source_metadata(path: Path, candidate: str) -> None:
    validate_candidate(candidate)
    _atomic_write(path, f'repository = "{REPOSITORY}"\ncommit = "{candidate}"\n')


def _ensure_targets_clean(root: Path) -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", *UPDATE_PATHS],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    if result.stdout:
        raise ValueError("gstack update targets contain uncommitted changes")


def _run_trusted_integration_gate(root: Path, candidate: str) -> None:
    validate_candidate(candidate)
    validate_vendor_tree(root / "vendor/gstack")
    _validate_generated_tree(root, _catalog_generated_root(root, "full"), "full")
    _validate_generated_tree(root, _catalog_generated_root(root, "workflow"), "workflow")

    source = _gstack_source(root)
    if source["commit"] != candidate:
        raise ValueError("installed gstack lock does not match candidate")
    with (root / "vendor/gstack-source.toml").open("rb") as handle:
        metadata = tomllib.load(handle)
    if metadata != {"repository": REPOSITORY, "commit": candidate}:
        raise ValueError("installed gstack source metadata does not match candidate")

    validator = root / "scripts/validate.py"
    if not validator.is_file() or validator.is_symlink():
        raise ValueError("trusted repository validator is missing or unsafe")
    result = subprocess.run(
        [sys.executable, str(validator)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        detail = result.stdout.strip() or f"exit status {result.returncode}"
        raise RuntimeError(f"trusted repository validation failed: {detail}")


def _install_update(
    root: Path,
    candidate: str,
    staged_vendor: Path,
    staged_full: Path,
    staged_workflow: Path,
) -> None:
    vendor_target = root / "vendor/gstack"
    full_target = _catalog_generated_root(root, "full")
    workflow_target = _catalog_generated_root(root, "workflow")
    lock_path = root / "sources.lock.toml"
    metadata_path = root / "vendor/gstack-source.toml"
    lock_before = _read_text_exact(lock_path)
    metadata_before = _read_text_exact(metadata_path)
    replacements = (
        (staged_vendor, vendor_target),
        (staged_full, full_target),
        (staged_workflow, workflow_target),
    )
    backups: list[tuple[Path, Path]] = []

    try:
        for _staged, target in replacements:
            if target.is_symlink() or not target.is_dir():
                raise ValueError(f"gstack update target is not a directory: {target}")
            backup = target.with_name(f".{target.name}.transaction-{uuid.uuid4().hex}")
            os.replace(target, backup)
            backups.append((target, backup))
    except BaseException:
        for target, backup in reversed(backups):
            os.replace(backup, target)
        raise

    try:
        replace_directory(staged_vendor, vendor_target)
        replace_directory(staged_full, full_target)
        replace_directory(staged_workflow, workflow_target)
        update_lock_commit(lock_path, candidate)
        write_source_metadata(metadata_path, candidate)
        _run_trusted_integration_gate(root, candidate)
    except BaseException:
        rollback_error: BaseException | None = None
        for staged, target in reversed(replacements):
            try:
                if target.exists():
                    if staged.exists():
                        shutil.rmtree(staged)
                    os.replace(target, staged)
            except BaseException as error:
                rollback_error = rollback_error or error
        for target, backup in reversed(backups):
            try:
                os.replace(backup, target)
            except BaseException as error:
                rollback_error = rollback_error or error
        try:
            if _read_text_exact(lock_path) != lock_before:
                _atomic_write(lock_path, lock_before)
            if _read_text_exact(metadata_path) != metadata_before:
                _atomic_write(metadata_path, metadata_before)
        except BaseException as error:
            rollback_error = rollback_error or error
        if rollback_error is not None:
            raise RuntimeError(f"gstack update rollback failed: {rollback_error}") from rollback_error
        raise
    else:
        for _target, backup in backups:
            try:
                shutil.rmtree(backup)
            except OSError as error:
                print(f"warning: update applied but backup cleanup failed for {backup}: {error}", file=sys.stderr)


def prepare_update(root: Path, candidate: str, archive: Path) -> None:
    root = root.resolve()
    validate_candidate(candidate)
    _ensure_targets_clean(root)

    with tempfile.TemporaryDirectory(prefix="gstack-extract-") as extraction_directory:
        extracted = extract_archive(archive, Path(extraction_directory) / "archive")
        expected_root = f"gstack-{candidate}"
        if extracted.name != expected_root:
            raise ValueError(
                f"archive root does not match candidate: expected {expected_root}, got {extracted.name}"
            )
        validate_vendor_tree(extracted)
        _validate_candidate_inventory(root, extracted)

        vendor_parent = root / "vendor"
        generated_parent = root / "generated"
        if not vendor_parent.is_dir() or vendor_parent.is_symlink():
            raise ValueError("repository vendor directory is missing or unsafe")
        if not generated_parent.is_dir() or generated_parent.is_symlink():
            raise ValueError("repository generated directory is missing or unsafe")
        staged_vendor = Path(tempfile.mkdtemp(prefix=".gstack-stage-", dir=vendor_parent))
        staged_full = Path(tempfile.mkdtemp(prefix=".gstack-codex-stage-", dir=generated_parent))
        staged_workflow = Path(
            tempfile.mkdtemp(prefix=".gstack-codex-workflow-stage-", dir=generated_parent)
        )
        try:
            shutil.copytree(extracted, staged_vendor, dirs_exist_ok=True)
            validate_vendor_tree(staged_vendor)
            generate_codex_skills(root, staged_vendor, staged_full, "full")
            generate_codex_skills(root, staged_vendor, staged_workflow, "workflow")
            validate_vendor_tree(staged_vendor)
            _validate_generated_tree(root, staged_full, "full")
            _validate_generated_tree(root, staged_workflow, "workflow")

            _install_update(
                root, candidate, staged_vendor, staged_full, staged_workflow
            )
        finally:
            if staged_vendor.exists():
                shutil.rmtree(staged_vendor)
            if staged_full.exists():
                shutil.rmtree(staged_full)
            if staged_workflow.exists():
                shutil.rmtree(staged_workflow)


def _gstack_source(root: Path) -> dict:
    with (root / "sources.lock.toml").open("rb") as handle:
        lock = tomllib.load(handle)
    sources = [source for source in lock.get("sources", []) if source.get("name") == "gstack"]
    if len(sources) != 1 or sources[0].get("repository") != REPOSITORY:
        raise ValueError("sources.lock.toml must contain the expected gstack source")
    validate_candidate(str(sources[0].get("commit", "")))
    return sources[0]


def upstream_candidate(root: Path) -> tuple[str, str]:
    source = _gstack_source(root)
    output = subprocess.check_output(
        ["git", "ls-remote", source["repository"], "HEAD"],
        text=True,
        stderr=subprocess.STDOUT,
    )
    fields = output.split()
    if len(fields) < 2 or fields[1] != "HEAD":
        raise ValueError("git ls-remote returned an invalid gstack HEAD")
    candidate = fields[0]
    validate_candidate(candidate)
    return source["commit"], candidate


def download_archive(candidate: str, destination: Path) -> None:
    validate_candidate(candidate)
    url = f"{REPOSITORY}/archive/{candidate}.tar.gz"
    with urllib.request.urlopen(url, timeout=30) as response, destination.open("xb") as output:
        shutil.copyfileobj(response, output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="show pinned and upstream commits without changing files")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        pinned, candidate = upstream_candidate(root)
        print(f"pinned:   {pinned}")
        print(f"upstream: {candidate}")
        if args.check:
            return 0 if pinned == candidate else 1
        if pinned == candidate:
            print("gstack is current")
            return 0
        with tempfile.TemporaryDirectory(prefix="gstack-download-") as directory:
            archive = Path(directory) / "gstack.tar.gz"
            download_archive(candidate, archive)
            prepare_update(root, candidate, archive)
        print("Prepared gstack update for review; no commit was created.")
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError, tarfile.TarError, tomllib.TOMLDecodeError) as error:
        print(f"gstack update failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
