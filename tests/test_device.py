"""Tests for device discovery and the gvfs (Linux MTP) backup layout."""

from pathlib import Path

import src.device as device


def test_find_whatsapp_root_android_media(tmp_path: Path):
    wa = tmp_path / "Internal shared storage" / "Android/media/com.whatsapp/WhatsApp"
    (wa / "Media").mkdir(parents=True)
    assert device._find_whatsapp_root(tmp_path) == wa


def test_find_whatsapp_root_legacy_layout(tmp_path: Path):
    wa = tmp_path / "Internal storage" / "WhatsApp"
    (wa / "Media").mkdir(parents=True)
    assert device._find_whatsapp_root(tmp_path) == wa


def test_gvfs_targets_mirrors_layout(tmp_path: Path):
    root = tmp_path / "WhatsApp"
    (root / "Databases").mkdir(parents=True)
    (root / "Databases" / "msgstore.db.crypt15").write_bytes(b"db")
    (root / "Media/WhatsApp Images/Sent").mkdir(parents=True)
    (root / "Media/WhatsApp Images/a.jpg").write_bytes(b"x")
    (root / "Media/WhatsApp Images/Sent/b.jpg").write_bytes(b"y")
    (root / "Media/WhatsApp Images/.hidden.jpg").write_bytes(b"h")
    (root / "Media/WhatsApp Video").mkdir(parents=True)
    (root / "Media/WhatsApp Video/c.mp4").write_bytes(b"z")

    dest = tmp_path / "out"
    targets = device._gvfs_targets(root, dest, ["WhatsApp Images", "WhatsApp Video"])
    rel = sorted(str(d.relative_to(dest)) for _, d in targets)

    assert rel == [
        "Databases/msgstore.db.crypt15",
        "Media/WhatsApp Images/Sent/b.jpg",
        "Media/WhatsApp Images/a.jpg",
        "Media/WhatsApp Video/c.mp4",
    ]


def test_gvfs_targets_skips_unselected_and_missing(tmp_path: Path):
    root = tmp_path / "WhatsApp"
    (root / "Media/WhatsApp Images").mkdir(parents=True)
    (root / "Media/WhatsApp Images/a.jpg").write_bytes(b"x")

    targets = device._gvfs_targets(root, tmp_path / "out", ["WhatsApp Images", "WhatsApp Video"])
    assert [d.name for _, d in targets] == ["a.jpg"]


def test_gio_mtp_uri_parsing(monkeypatch):
    sample = (
        "Drive(0): Fairphone 4\n"
        "  Type: GProxyDrive (GProxyVolumeMonitorMTP)\n"
        "  Volume(0): Fairphone 4\n"
        "    Type: GProxyVolume (GProxyVolumeMonitorMTP)\n"
        "    Mount(0): Fairphone 4 <mtp://[usb:002,003]/>\n"
        "      Type: GProxyMount (GProxyVolumeMonitorMTP)\n"
    )

    class Result:
        stdout = sample

    monkeypatch.setattr(device.shutil, "which", lambda name: "/usr/bin/gio")
    monkeypatch.setattr(device.subprocess, "run", lambda *a, **k: Result())

    assert device._gio_mtp_uris() == [("mtp://[usb:002,003]/", "Fairphone 4")]
