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
    "sources.lock.toml",
)


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


def _validate_generated_tree(root: Path, generated: Path) -> None:
    expected = _catalog_skill_names(root)
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
        trusted_skill = root / "generated/gstack-codex" / name / "SKILL.md"
        if trusted_skill.is_file() and not trusted_skill.is_symlink():
            trusted_text = trusted_skill.read_text(encoding="utf-8")
            for initialization in ("GSTACK_ROOT=", "GSTACK_BIN="):
                if initialization in trusted_text and initialization not in frontmatter:
                    raise ValueError(
                        f"generated gstack skill is missing {initialization.rstrip('=')}: {name}"
                    )
        if "{{" in frontmatter or "}}" in frontmatter:
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


def _adapt_codex_skill(source: str, name: str) -> str:
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
    if preamble in body and "GSTACK_ROOT=" not in body:
        body = body.replace(preamble, preamble + initialization, 1)
    adapted = f"---\nname: {name}\n{description}\n---\n{body}"
    for old, new in (
        ("~/.claude/skills/gstack", "$GSTACK_ROOT"),
        (".claude/skills/gstack", ".agents/skills/gstack"),
        (".claude/skills/review", ".agents/skills/gstack/review"),
        (".claude/skills", ".agents/skills"),
    ):
        adapted = adapted.replace(old, new)
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


def generate_codex_skills(root: Path, staged_vendor: Path, staged_generated: Path) -> None:
    trusted_generated = root / "generated/gstack-codex"
    trusted_vendor = root / "vendor/gstack"
    for name in sorted(_catalog_skill_names(root)):
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
            adapted = _adapt_codex_skill(source.read_text(encoding="utf-8"), name)
            trusted_skill = fallback / "SKILL.md"
            if (
                trusted_source.is_file()
                and not trusted_source.is_symlink()
                and trusted_skill.is_file()
                and not trusted_skill.is_symlink()
            ):
                adapted = _suppress_trusted_codex_sections(
                    adapted,
                    _adapt_codex_skill(trusted_source.read_text(encoding="utf-8"), name),
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


def _install_update(root: Path, candidate: str, staged_vendor: Path, staged_generated: Path) -> None:
    vendor_target = root / "vendor/gstack"
    generated_target = root / "generated/gstack-codex"
    lock_path = root / "sources.lock.toml"
    metadata_path = root / "vendor/gstack-source.toml"
    lock_before = _read_text_exact(lock_path)
    metadata_before = _read_text_exact(metadata_path)
    replacements = (
        (staged_vendor, vendor_target),
        (staged_generated, generated_target),
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
        replace_directory(staged_generated, generated_target)
        update_lock_commit(lock_path, candidate)
        write_source_metadata(metadata_path, candidate)
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
        validate_vendor_tree(extracted)

        vendor_parent = root / "vendor"
        generated_parent = root / "generated"
        if not vendor_parent.is_dir() or vendor_parent.is_symlink():
            raise ValueError("repository vendor directory is missing or unsafe")
        if not generated_parent.is_dir() or generated_parent.is_symlink():
            raise ValueError("repository generated directory is missing or unsafe")
        staged_vendor = Path(tempfile.mkdtemp(prefix=".gstack-stage-", dir=vendor_parent))
        staged_generated = Path(tempfile.mkdtemp(prefix=".gstack-codex-stage-", dir=generated_parent))
        try:
            shutil.copytree(extracted, staged_vendor, dirs_exist_ok=True)
            validate_vendor_tree(staged_vendor)
            generate_codex_skills(root, staged_vendor, staged_generated)
            validate_vendor_tree(staged_vendor)
            _validate_generated_tree(root, staged_generated)

            _install_update(root, candidate, staged_vendor, staged_generated)
        finally:
            if staged_vendor.exists():
                shutil.rmtree(staged_vendor)
            if staged_generated.exists():
                shutil.rmtree(staged_generated)


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
