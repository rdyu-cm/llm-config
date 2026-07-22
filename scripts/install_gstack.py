import argparse
import json
import sys
import tomllib
from pathlib import Path


STATE_RELATIVE = Path(".codex/gstack-managed.json")


def load_catalog(root: Path) -> dict:
    with (root / "gstack-capabilities.toml").open("rb") as handle:
        return tomllib.load(handle)


def desired_links(root: Path, home: Path, mode: str) -> dict[Path, Path]:
    if mode == "off":
        return {}
    catalog = load_catalog(root)
    skills = catalog["profiles"][mode]["skills"]
    links = {
        home / ".codex" / "skills" / name: root / "generated" / "gstack-codex" / name
        for name in skills
    }
    runtime = home / ".codex" / "skills" / "gstack"
    links[runtime / "bin"] = root / "vendor" / "gstack" / "bin"
    links[runtime / "ETHOS.md"] = root / "vendor" / "gstack" / "ETHOS.md"
    links[runtime / "review"] = root / "vendor" / "gstack" / "review"
    if mode == "full":
        links[runtime / "browse"] = root / "vendor" / "gstack" / "browse"
        links[runtime / "qa"] = root / "vendor" / "gstack" / "qa"
        links[runtime / "design"] = root / "vendor" / "gstack" / "design"
        links[runtime / "make-pdf"] = root / "vendor" / "gstack" / "make-pdf"
    return links


def _lexists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _parent_conflicts(home: Path, target: Path) -> list[Path]:
    conflicts: list[Path] = []
    current = home
    for part in target.parent.relative_to(home).parts:
        current /= part
        if not _lexists(current):
            break
        if current.is_symlink() or not current.is_dir():
            conflicts.append(current)
    return conflicts


def _load_state(path: Path) -> tuple[dict, bytes | None]:
    if not _lexists(path):
        return {"version": 1, "links": {}}, None
    raw = path.read_bytes()
    state = json.loads(raw)
    if state.get("version") != 1 or not isinstance(state.get("links"), dict):
        raise ValueError("invalid gstack managed state")
    return state, raw


def _matches_recorded_link(target: Path, source: str) -> bool:
    return target.is_symlink() and target.resolve() == Path(source).resolve()


def _write_state(path: Path, state: dict) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _restore_state(path: Path, previous: bytes | None) -> None:
    if previous is None:
        path.unlink(missing_ok=True)
        return
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_bytes(previous)
    temporary.replace(path)


def install(root: Path, home: Path, mode: str, apply: bool) -> list[str]:
    if mode not in {"off", "workflow", "full"}:
        raise ValueError(f"invalid gstack mode: {mode}")

    root = root.resolve()
    home = home.resolve()
    desired = {target: source.resolve() for target, source in desired_links(root, home, mode).items()}
    state_path = home / STATE_RELATIVE
    messages: list[str] = []

    for target in desired:
        for parent in _parent_conflicts(home, target):
            messages.append(f"conflict: {parent}")
    for parent in _parent_conflicts(home, state_path):
        messages.append(f"conflict: {parent}")
    if _lexists(state_path) and (state_path.is_symlink() or not state_path.is_file()):
        messages.append(f"conflict: {state_path}")
    temporary = state_path.with_name(f"{state_path.name}.tmp")
    if _lexists(temporary):
        messages.append(f"conflict: {temporary}")
    if messages:
        return messages

    state, previous_state = _load_state(state_path)
    recorded = {Path(target): source for target, source in state["links"].items()}
    for target in desired:
        if _lexists(target) and not _matches_recorded_link(target, recorded.get(target, "")):
            messages.append(f"conflict: {target}")
    if messages:
        return messages

    if not apply:
        messages.extend(f"would link {target} -> {source}" for target, source in desired.items())
        messages.extend(f"would remove {target}" for target, source in recorded.items() if target not in desired and _matches_recorded_link(target, source))
        return messages

    created: list[Path] = []
    replaced: list[tuple[Path, str]] = []
    removed: list[tuple[Path, str]] = []
    try:
        for target, source in desired.items():
            if target.is_symlink() and _matches_recorded_link(target, recorded.get(target, "")) and target.resolve() == source:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                replaced.append((target, recorded[target]))
                target.unlink()
            target.symlink_to(source, target_is_directory=source.is_dir())
            created.append(target)
            messages.append(f"linked {target} -> {source}")

        for target, source in recorded.items():
            if target not in desired and _matches_recorded_link(target, source):
                removed.append((target, source))
                target.unlink()
                messages.append(f"removed {target}")

        state_path.parent.mkdir(parents=True, exist_ok=True)
        _write_state(state_path, {
            "version": 1,
            "mode": mode,
            "links": {str(target): str(source) for target, source in desired.items()},
        })
    except OSError:
        for target in created:
            if target.is_symlink():
                target.unlink()
        for target, source in replaced:
            target.symlink_to(source, target_is_directory=Path(source).is_dir())
        for target, source in removed:
            if not _lexists(target):
                target.symlink_to(source, target_is_directory=Path(source).is_dir())
        _restore_state(state_path, previous_state)
        raise
    return messages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--mode", choices=("off", "workflow", "full"), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        messages = install(args.root.resolve(), Path.home(), args.mode, args.apply)
        for message in messages:
            print(message)
        if args.apply and any(message.startswith("conflict:") for message in messages):
            return 1
    except (OSError, ValueError, tomllib.TOMLDecodeError) as error:
        print(f"gstack install failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
