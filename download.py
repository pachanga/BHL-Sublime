"""Download and install prebuilt BHL LSP binaries from GitHub releases."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from typing import Callable, Dict, List, Optional

RELEASES_URL = "https://api.github.com/repos/bitdotgames/BHL/releases?per_page=30"
USER_AGENT = "BHL-Sublime-Package"
TAG_PREFIX = "lsp-v"
TIMEOUT = 30

Release = Dict[str, object]
Progress = Callable[[str], None]


def release_version(tag_name: str) -> str:
    """`lsp-v0.3.1` -> `v0.3.1`"""
    return tag_name[len("lsp-"):] if tag_name.startswith("lsp-") else tag_name


def current_platform_suffix() -> Optional[str]:
    """e.g. `osx-arm64`, `linux-x64`, `win-x64`; None if no asset is published for this platform."""
    system = platform.system()
    os_name = {"Darwin": "osx", "Windows": "win", "Linux": "linux"}.get(system)
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "amd64": "x64"}.get(platform.machine().lower())
    if not os_name or not arch:
        return None
    if os_name == "win" and arch == "arm64":
        return None
    return "{}-{}".format(os_name, arch)


def _binary_name(suffix: str) -> str:
    return "bhl.exe" if suffix.startswith("win") else "bhl"


def _open(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(request, timeout=TIMEOUT)


def fetch_releases() -> List[Release]:
    """All non-draft `lsp-v*` releases, newest first."""
    with _open(RELEASES_URL) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return [r for r in raw if not r.get("draft") and str(r.get("tag_name", "")).startswith(TAG_PREFIX)]


def _find_asset(release: Release, suffix: str) -> Optional[dict]:
    for asset in release.get("assets") or []:  # type: ignore[attr-defined]
        name = asset["name"]
        if name.endswith("-{}.tar.gz".format(suffix)) or name.endswith("-{}.zip".format(suffix)):
            return asset
    return None


def _find_checksum_asset(release: Release, asset: dict) -> Optional[dict]:
    name = asset["name"]
    for ext in (".tar.gz", ".zip"):
        if name.endswith(ext):
            name = name[:-len(ext)]
            break
    for candidate in release.get("assets") or []:  # type: ignore[attr-defined]
        if candidate["name"] == name + ".sha256":
            return candidate
    return None


def installed_binary(installs_root: str) -> Optional[str]:
    """Path to the downloaded binary under `installs_root/<tag>/<suffix>/bhl[.exe]`, if any."""
    suffix = current_platform_suffix()
    if not suffix or not os.path.isdir(installs_root):
        return None
    for tag in sorted(os.listdir(installs_root), reverse=True):
        candidate = os.path.join(installs_root, tag, suffix, _binary_name(suffix))
        if os.path.isfile(candidate):
            return candidate
    return None


def version_from_binary_path(binary_path: Optional[str]) -> Optional[str]:
    if not binary_path:
        return None
    tag = os.path.basename(os.path.dirname(os.path.dirname(binary_path)))
    return release_version(tag) if tag.startswith("lsp-") else None


def remove_installs(installs_root: str) -> None:
    shutil.rmtree(installs_root, ignore_errors=True)


def _cleanup_other_installs(installs_root: str, keep_tag: str) -> None:
    if not os.path.isdir(installs_root):
        return
    for entry in os.listdir(installs_root):
        if entry != keep_tag:
            shutil.rmtree(os.path.join(installs_root, entry), ignore_errors=True)


def _download(url: str, dest: str, on_progress: Progress, label: str) -> None:
    with _open(url) as response, open(dest, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        received = 0
        last_pct = -1
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            out.write(chunk)
            received += len(chunk)
            if total and received * 100 // total != last_pct:
                last_pct = received * 100 // total
                on_progress("Downloading {}… {}%".format(label, last_pct))


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_single_binary(archive: str, name: str, destination: str) -> None:
    """Every published archive contains exactly one file: the `bhl`/`bhl.exe` executable."""
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            members = [m for m in zf.infolist() if not m.is_dir()]
            if not members:
                raise RuntimeError("{} is empty".format(name))
            with zf.open(members[0]) as src, open(destination, "wb") as dst:
                shutil.copyfileobj(src, dst)
    else:
        with tarfile.open(archive) as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            if not members:
                raise RuntimeError("{} is empty".format(name))
            src = tf.extractfile(members[0])
            assert src is not None
            with src, open(destination, "wb") as dst:
                shutil.copyfileobj(src, dst)


def install_release(release: Release, installs_root: str, on_progress: Progress) -> str:
    """
    Downloads, verifies (against the release's `.sha256` sibling asset) and extracts the binary
    for the current platform, returning the path to the executable. No-op if already installed.
    """
    suffix = current_platform_suffix()
    if not suffix:
        raise RuntimeError("No BHL binary is published for this platform ({} {})".format(
            platform.system(), platform.machine()))
    tag = str(release["tag_name"])
    asset = _find_asset(release, suffix)
    if not asset:
        raise RuntimeError("Release {} has no binary for {}".format(tag, suffix))

    _cleanup_other_installs(installs_root, tag)

    install_dir = os.path.join(installs_root, tag, suffix)
    binary_path = os.path.join(install_dir, _binary_name(suffix))
    if os.path.isfile(binary_path):
        return binary_path

    # Verify before touching the final location: a failed install must not leave a runnable binary.
    checksum_asset = _find_checksum_asset(release, asset)
    if not checksum_asset:
        # Mandatory: the binary runs unsandboxed, so never install it unverified.
        raise RuntimeError("{} has no .sha256 checksum for {} — refusing to install unverified".format(
            tag, asset["name"]))

    os.makedirs(install_dir, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(dir=install_dir) as scratch:
            archive = os.path.join(scratch, asset["name"])
            on_progress("Downloading {}…".format(asset["name"]))
            _download(asset["browser_download_url"], archive, on_progress, asset["name"])

            on_progress("Verifying checksum…")
            with _open(checksum_asset["browser_download_url"]) as response:
                expected = response.read().decode("utf-8").strip().split()[0].lower()
            actual = _sha256(archive)
            if expected != actual:
                raise RuntimeError("Checksum mismatch for {}: expected {}, got {}".format(
                    asset["name"], expected, actual))

            on_progress("Extracting {}…".format(asset["name"]))
            staged = os.path.join(scratch, _binary_name(suffix))
            _extract_single_binary(archive, asset["name"], staged)
            os.chmod(staged, 0o755)
            if suffix.startswith("osx"):
                # Gatekeeper may refuse a quarantined, unsigned binary; `xattr -d` fails if absent.
                subprocess.run(["xattr", "-d", "com.apple.quarantine", staged],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.replace(staged, binary_path)
    except BaseException:
        shutil.rmtree(os.path.join(installs_root, tag), ignore_errors=True)
        raise
    return binary_path
