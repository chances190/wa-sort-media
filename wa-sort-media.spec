# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the WhatsApp Media Suite GUI.

Build (from the repo root):

    uv run --group build pyinstaller --noconfirm --clean wa-sort-media.spec

Output: dist/WhatsApp Media Suite/  (one-dir bundle, shipped via installer/).

One-dir is preferred over one-file: it starts faster and trips antivirus /
SmartScreen far less often. pywebview ships its own PyInstaller hook
(webview/__pyinstaller) which bundles its JS + native DLLs automatically.
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)

# get_base_path() resolves resources from sys._MEIPASS when frozen, so the
# assets and runtime PowerShell scripts must live at these relative paths in
# the bundle. Listed explicitly so build tooling (scripts/build.ps1) stays out.
datas = [
    (str(ROOT / "gui" / "assets"), "gui/assets"),
    (str(ROOT / "scripts" / "Get-MTPDevices.ps1"), "scripts"),
    (str(ROOT / "scripts" / "MTP-Copy.ps1"), "scripts"),
]

hiddenimports = collect_submodules("wa_crypt_tools")

if sys.platform == "win32":
    # pywebview selects its backend dynamically, so PyInstaller cannot see it.
    hiddenimports += ["webview.platforms.winforms", "webview.platforms.edgechromium"]

a = Analysis(
    ["gui/main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WhatsApp Media Suite",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="WhatsApp Media Suite",
)
