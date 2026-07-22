import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import platform
import urllib.request
from pathlib import Path


def load_catalog(root: Path) -> dict:
    with (root / "gstack-capabilities.toml").open("rb") as handle:
        return tomllib.load(handle)


def find_bun(env: dict[str, str]) -> Path | None:
    bun = shutil.which("bun", path=env.get("PATH"))
    return Path(bun) if bun else None


def download_installer() -> Path:
    with urllib.request.urlopen("https://bun.sh/install", timeout=15) as response, \
         tempfile.NamedTemporaryFile(delete=False) as installer:
        shutil.copyfileobj(response, installer)
        return Path(installer.name)


def verify_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise ValueError("Bun installer checksum mismatch")


def run_bun_installer(installer: Path, version: str, env: dict[str, str]) -> None:
    subprocess.run(["bash", str(installer), f"bun-v{version}"], env=env, check=True)

def host_platform() -> tuple[str, str, str, str]:
    values: dict[str, str] = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key] = value.strip().strip('"')
    except OSError:
        pass
    return platform.system().lower(), platform.machine().lower(), values.get("ID", ""), values.get("VERSION_ID", "")


def prepare(root: Path, mode: str, apply: bool, env: dict[str, str]) -> list[str]:
    if mode not in {"off", "workflow", "full"}:
        raise ValueError(f"invalid gstack mode: {mode}")
    if mode == "off":
        return []

    catalog = load_catalog(root)
    bun = find_bun(env)
    messages: list[str] = []
    if bun is None:
        if not apply:
            return [f"would   install Bun {catalog['bun']['version']}"]
        installer = download_installer()
        try:
            verify_sha256(installer, catalog["bun"]["installer_sha256"])
            run_bun_installer(installer, catalog["bun"]["version"], env)
        finally:
            try:
                installer.unlink(missing_ok=True)
            except OSError:
                pass
        bun_home = Path(env.get("HOME") or Path.home())
        installed_path = f"{bun_home / '.bun/bin'}{os.pathsep}{env.get('PATH', '')}"
        bun = find_bun(env | {"PATH": installed_path})
        if bun is None:
            raise RuntimeError("Bun installation completed but bun is unavailable")
    if not apply:
        return messages + [f"would   prepare gstack {mode}"]
    if mode == "workflow":
        return [f"ready   gstack {mode}"] if apply else [f"would   prepare gstack {mode}"]
    child_env = dict(env)
    subprocess.run(
        [str(bun), "install", "--frozen-lockfile"],
        cwd=root / "vendor/gstack",
        env=child_env,
        check=True,
    )
    subprocess.run([str(bun), "run", "build"], cwd=root / "vendor/gstack", env=child_env, check=True)
    browser_env = dict(child_env)
    if host_platform() == ("linux", "x86_64", "ubuntu", "26.04"):
        browser_env["PLAYWRIGHT_HOST_PLATFORM_OVERRIDE"] = "ubuntu24.04-x64"
        print("warning: Ubuntu 26.04 Chromium is unavailable; using Playwright Ubuntu 24.04 binaries", file=sys.stderr)
    subprocess.run(
        [str(bun), "x", "playwright", "install", "chromium"],
        cwd=root / "vendor/gstack",
        env=browser_env,
        check=True,
    )
    return messages + [f"ready   gstack {mode}"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--mode", choices=("off", "workflow", "full"), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        for message in prepare(args.root.resolve(), args.mode, args.apply, dict(os.environ)):
            print(message)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError, tomllib.TOMLDecodeError) as error:
        print(f"gstack preparation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
