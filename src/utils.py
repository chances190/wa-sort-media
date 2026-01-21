"""Utility helpers: name sanitization and phone formatting."""

from __future__ import annotations
import re


def sanitize_dir_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "unknown"

    # 1. Remove Windows-illegal characters: [< > : " / \ | ? *] and control characters (0-31)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)

    # 2. Strip trailing dots and spaces (forbidden in Windows)
    name = name.rstrip(". ")

    # 3. Handle Windows reserved device names (CON, PRN, etc.) and hidden file prefix
    if re.match(
        r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$", name, re.IGNORECASE
    ) or name.startswith((".", "-")):
        name = f"_{name}"

    return name[:255] or "unknown"
