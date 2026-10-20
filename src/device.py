"""Device discovery and backup.

Backends, in order of preference per platform (so layman users need no extra
phone setup):

* Windows  -> ``mtp``  : PowerShell Shell COM (zero setup)
* Linux    -> ``gvfs`` : the desktop's MTP mount under /run/user/$UID/gvfs
* anywhere -> ``adb``  : fallback, requires USB debugging (e.g. macOS)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

ANDROID_WHATSAPP_ROOT = "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp"

# Databases is always copied because the decrypt step needs msgstore.db.crypt15.
DATABASES_PART = "Databases"
MEDIA_PART = "Media"
CRYPT_DB_NAME = "msgstore.db.crypt15"

MEDIA_FOLDERS: tuple[str, ...] = (
    "WhatsApp Images",
    "WhatsApp Video",
    "WhatsApp Audio",
    "WhatsApp Voice Notes",
    "WhatsApp Video Notes",
    "WhatsApp Documents",
    "WhatsApp Stickers",
    "WhatsApp Animated Gifs",
)

# Layouts the WhatsApp folder might live at, relative to the storage root.
_WHATSAPP_REL_PATHS = ("Android/media/com.whatsapp/WhatsApp", "WhatsApp")

Emit = Callable[..., None]
ProcSink = Callable[[subprocess.Popen], None]

# One file done, e.g. "/dest/IMG-1.jpg: 1 file pulled, 0 skipped. ..."
_PULLED = re.compile(r"^(?P<path>.+?):\s*\d+\s+files?\s+pulled")


@dataclass(frozen=True, slots=True)
class Device:
    id: str
    label: str
    backend: str  # "mtp" | "gvfs" | "adb"


def list_devices(scripts_dir: Path) -> list[Device]:
    """Return devices for the preferred backend on this platform."""
    if sys.platform == "win32":
        devices = _list_mtp_devices(scripts_dir)
        if devices:
            return devices
    elif sys.platform.startswith("linux"):
        devices = _list_gvfs_devices()
        if devices:
            return devices
    return _list_adb_devices()


def pull_backup(
    device: Device,
    destination: Path,
    emit: Emit,
    *,
    scripts_dir: Path,
    media_folders: Sequence[str] = MEDIA_FOLDERS,
    skip_existing: bool = False,
    on_proc: ProcSink | None = None,
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if device.backend == "adb":
        _pull_adb(device, destination, emit, media_folders, on_proc)
    elif device.backend == "gvfs":
        _pull_gvfs(device, destination, emit, media_folders, skip_existing)
    else:
        _pull_mtp(device, destination, scripts_dir, emit, media_folders, skip_existing, on_proc)


# ---------------------------------------------------------------------------
# MTP via Shell COM (Windows)
# ---------------------------------------------------------------------------


def _list_mtp_devices(scripts_dir: Path) -> list[Device]:
    try:
        proc = subprocess.run(
            [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(scripts_dir / "Get-MTPDevices.ps1"),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [
        Device(id=name.strip(), label=name.strip(), backend="mtp")
        for name in proc.stdout.splitlines()
        if name.strip()
    ]


def _pull_mtp(
    device: Device,
    destination: Path,
    scripts_dir: Path,
    emit: Emit,
    media_folders: Sequence[str],
    skip_existing: bool,
    on_proc: ProcSink | None,
) -> None:
    cmd = [
        "powershell.exe",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(scripts_dir / "MTP-Copy.ps1"),
        "-deviceName",
        device.id,
        "-destinationPath",
        str(destination),
        "-mediaFolders",
        *media_folders,
    ]
    if skip_existing:
        cmd.append("-skipExisting")

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    if on_proc:
        on_proc(proc)

    for raw in proc.stdout:
        line = raw.strip()
        if not line:
            continue
        if "[PROGRESS]" in line:
            current, total = _parse_mtp_progress(line)
            emit("progress", current=current, total=total)
        elif "[FILE]" in line:
            emit("file", name=line.split("[FILE]", 1)[1].strip())
        else:
            emit("log", message=line)

    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Copying stopped unexpectedly. Try again, or export diagnostics for details.")


def _parse_mtp_progress(line: str) -> tuple[int, int]:
    part = line.split("[PROGRESS]", 1)[1].strip()
    try:
        current, total = part.split("/", 1)
        return int(current.strip()), int(total.strip())
    except ValueError:
        return 0, 0


# ---------------------------------------------------------------------------
# MTP via gvfs (Linux)
# ---------------------------------------------------------------------------


def _gvfs_dir() -> Path:
    return Path(f"/run/user/{os.getuid()}/gvfs")


def _list_gvfs_devices() -> list[Device]:
    devices: list[Device] = []
    gvfs = _gvfs_dir()
    if gvfs.is_dir():
        for entry in sorted(gvfs.glob("mtp:*")):
            if entry.is_dir():
                devices.append(Device(id=str(entry), label=_gvfs_label(entry.name), backend="gvfs"))
    if devices:
        return devices
    # Not mounted yet: offer whatever gvfs knows about so we can mount on demand.
    return [Device(id=uri, label=label, backend="gvfs") for uri, label in _gio_mtp_uris()]


def _gvfs_label(name: str) -> str:
    return name.removeprefix("mtp:host=").replace("_", " ") or name


def _gio_mtp_uris() -> list[tuple[str, str]]:
    if not shutil.which("gio"):
        return []
    try:
        proc = subprocess.run(["gio", "mount", "-li"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return []

    found: list[tuple[str, str]] = []
    label = "Android device"
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("Volume(") and ":" in stripped:
            label = stripped.split(":", 1)[1].strip()
        elif "mtp://" in stripped and "<" in stripped:
            uri = stripped[stripped.index("<") + 1 : stripped.index(">")]
            found.append((uri, label))
    return found


def _mount_gvfs(uri: str) -> Path:
    subprocess.run(["gio", "mount", uri], capture_output=True, text=True, timeout=60)
    for entry in _gvfs_dir().glob("mtp:*"):
        return entry
    raise RuntimeError("Couldn't open the phone. Make sure it's connected, unlocked and set to File transfer.")


def _pull_gvfs(
    device: Device,
    destination: Path,
    emit: Emit,
    media_folders: Sequence[str],
    skip_existing: bool,
) -> None:
    mount = Path(device.id) if device.id.startswith("/") else _mount_gvfs(device.id)
    root = _find_whatsapp_root(mount)
    if root is None:
        raise RuntimeError("Couldn't find WhatsApp on the phone.")

    targets = _gvfs_targets(root, destination, media_folders)
    total = len(targets)
    emit("start", total=total)

    for done, (src, dest) in enumerate(targets, start=1):
        dest.parent.mkdir(parents=True, exist_ok=True)
        if skip_existing and dest.is_file() and dest.stat().st_size == src.stat().st_size:
            emit("progress", current=done, total=total)
            continue
        emit("file", name=src.name)
        # copyfile (not copy2): gvfs mounts often reject copying file metadata.
        shutil.copyfile(src, dest)
        emit("progress", current=done, total=total)

    emit("log", message="Finished all tasks.")


def _find_whatsapp_root(mount: Path) -> Path | None:
    for storage in sorted(p for p in mount.iterdir() if p.is_dir()):
        for rel in _WHATSAPP_REL_PATHS:
            candidate = storage / rel
            if candidate.is_dir():
                return candidate
    return None


def _gvfs_targets(
    root: Path, destination: Path, media_folders: Sequence[str]
) -> list[tuple[Path, Path]]:
    targets: list[tuple[Path, Path]] = []

    db = root / DATABASES_PART / CRYPT_DB_NAME
    if db.is_file():
        targets.append((db, destination / DATABASES_PART / CRYPT_DB_NAME))

    media = root / MEDIA_PART
    for folder in media_folders:
        folder_dir = media / folder
        if not folder_dir.is_dir():
            continue
        for src in sorted(folder_dir.rglob("*")):
            if src.is_file() and not src.name.startswith("."):
                targets.append((src, destination / MEDIA_PART / folder / src.relative_to(folder_dir)))

    return targets


# ---------------------------------------------------------------------------
# adb (fallback; requires USB debugging)
# ---------------------------------------------------------------------------


def _list_adb_devices() -> list[Device]:
    if not shutil.which("adb"):
        return []
    try:
        proc = subprocess.run(
            ["adb", "devices", "-l"], capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.SubprocessError):
        return []

    devices: list[Device] = []
    for line in proc.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2 or parts[1] != "device":
            continue
        serial = parts[0]
        model = next(
            (p[len("model:") :].replace("_", " ") for p in parts if p.startswith("model:")),
            serial,
        )
        devices.append(Device(id=serial, label=f"{model} ({serial})", backend="adb"))
    return devices


def _adb_media_paths(media_folders: Sequence[str]) -> list[str]:
    return [f"{ANDROID_WHATSAPP_ROOT}/{MEDIA_PART}/{folder}" for folder in media_folders]


def _pull_adb(
    device: Device,
    destination: Path,
    emit: Emit,
    media_folders: Sequence[str],
    on_proc: ProcSink | None,
) -> None:
    total = _adb_file_count(device, media_folders)
    emit("start", total=total)

    done = 0
    targets = [(f"{ANDROID_WHATSAPP_ROOT}/{DATABASES_PART}", destination / DATABASES_PART)]
    for folder in media_folders:
        targets.append(
            (f"{ANDROID_WHATSAPP_ROOT}/{MEDIA_PART}/{folder}", destination / MEDIA_PART / folder)
        )

    for remote, local in targets:
        local.mkdir(parents=True, exist_ok=True)
        emit("log", message=f"Pulling {local.name}...")

        proc = subprocess.Popen(
            ["adb", "-s", device.id, "pull", remote, str(local)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if on_proc:
            on_proc(proc)

        for raw in proc.stdout:
            line = raw.strip()
            if not line:
                continue
            match = _PULLED.match(line)
            if match:
                done += 1
                emit("file", name=Path(match.group("path")).name)
                emit("progress", current=done, total=max(total, done))
            elif line.lower().startswith("adb:") or "error" in line.lower():
                emit("log", message=line)

        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"Copying {local.name} failed (exit code {proc.returncode}).")

    emit("log", message="Finished all tasks.")


def _adb_file_count(device: Device, media_folders: Sequence[str]) -> int:
    roots = [f"{ANDROID_WHATSAPP_ROOT}/{DATABASES_PART}", *_adb_media_paths(media_folders)]
    try:
        proc = subprocess.run(
            ["adb", "-s", device.id, "shell", "find", *roots, "-type", "f"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    return sum(1 for line in proc.stdout.splitlines() if line.strip())
