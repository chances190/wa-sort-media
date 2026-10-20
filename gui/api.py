"""Bridge exposed to the webview frontend: devices, backup, decrypt, organize."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import webview

from src.contacts import load_vcf_contacts
from src.device import MEDIA_FOLDERS, Device, list_devices, pull_backup
from src.organizer import Organizer


def get_base_path() -> Path:
    """Root folder holding bundled resources (repo root, or PyInstaller _MEIPASS)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


class BackupAPI:
    """Methods exposed to JavaScript as window.pywebview.api.*"""

    def __init__(self) -> None:
        self._window: Any = None
        self._proc: subprocess.Popen | None = None
        self.running = False
        self.processed_files = 0
        self.total_files = 0
        self.last_error: str | None = None

    def set_window(self, window: Any) -> None:
        self._window = window

    def _emit(self, name: str, **data: Any) -> None:
        """Push a single structured event to the frontend."""
        if self._window is not None:
            payload = json.dumps({"name": name, "data": data})
            self._window.evaluate_js(f"window.__pyEvent({payload})")

    # ------------------------------------------------------------------
    # File / folder pickers (native dialogs)
    # ------------------------------------------------------------------

    def pick_folder(self) -> dict[str, Any]:
        return self._pick(webview.FileDialog.FOLDER)

    def pick_file(self, kind: str = "database") -> dict[str, Any]:
        file_types = (
            ("Contacts (*.vcf)", "All files (*.*)")
            if kind == "contacts"
            else ("WhatsApp database (*.db;*.crypt15)", "All files (*.*)")
        )
        return self._pick(webview.FileDialog.OPEN, file_types=file_types)

    def _pick(self, dialog_type: int, *, file_types: tuple[str, ...] = ()) -> dict[str, Any]:
        chosen = self._window.create_file_dialog(
            dialog_type, directory=str(Path.home()), file_types=file_types
        )
        if chosen:
            return {"success": True, "path": chosen[0]}
        return {"success": False, "path": None}

    def open_path(self, path: str) -> dict[str, Any]:
        target = Path(path)
        if not target.exists():
            return {"success": False, "error": f"Path does not exist: {path}"}
        try:
            if sys.platform == "win32":
                os.startfile(target)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
            return {"success": True}
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------

    def get_media_folders(self) -> dict[str, Any]:
        return {"folders": list(MEDIA_FOLDERS)}

    def get_devices(self) -> dict[str, Any]:
        try:
            devices = list_devices(get_base_path() / "scripts")
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": str(e), "devices": []}
        return {
            "success": True,
            "devices": [
                {"id": d.id, "label": d.label, "backend": d.backend} for d in devices
            ],
        }

    # ------------------------------------------------------------------
    # Space check
    # ------------------------------------------------------------------

    def check_space(self, media_path: str, output_path: str) -> dict[str, Any]:
        try:
            media = Path(media_path)
            needed = sum(
                f.stat().st_size for f in media.rglob("*") if f.is_file()
            )
            probe = Path(output_path)
            while not probe.exists() and probe != probe.parent:
                probe = probe.parent
            free = shutil.disk_usage(probe).free
            return {"success": True, "needed": needed, "free": free, "ok": free > needed}
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def start_backup(
        self,
        device_id: str,
        backend: str,
        destination: str,
        media_folders: list[str] | None = None,
        skip_existing: bool = False,
    ) -> dict[str, Any]:
        self.running = True
        self.processed_files = 0
        self.total_files = 0
        self.last_error = None
        device = Device(id=device_id, label=device_id, backend=backend)
        folders = media_folders if media_folders is not None else list(MEDIA_FOLDERS)
        threading.Thread(
            target=self._run_backup,
            args=(device, Path(destination), folders, skip_existing),
            daemon=True,
        ).start()
        return {"success": True, "backup_path": destination}

    def _run_backup(
        self,
        device: Device,
        destination: Path,
        media_folders: list[str],
        skip_existing: bool,
    ) -> None:
        def emit(kind: str, **data: Any) -> None:
            if kind in ("start", "progress"):
                self.processed_files = data.get("current", self.processed_files)
                self.total_files = data.get("total", self.total_files)
            self._emit(f"backup:{kind}", **data)

        try:
            pull_backup(
                device,
                destination,
                emit,
                scripts_dir=get_base_path() / "scripts",
                media_folders=media_folders,
                skip_existing=skip_existing,
                on_proc=lambda proc: setattr(self, "_proc", proc),
            )
            if self.running:
                self._emit("backup:complete", path=str(destination))
            else:
                self._emit("backup:canceled")
        except Exception as e:  # noqa: BLE001
            self.last_error = traceback.format_exc()
            if self.running:
                self._emit("backup:error", message=str(e))
            else:
                self._emit("backup:canceled")
        finally:
            self.running = False
            self._proc = None

    def cancel_backup(self) -> dict[str, Any]:
        self.running = False
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            return {"success": True}
        return {"success": False, "error": "No backup in progress"}

    # ------------------------------------------------------------------
    # Decrypt
    # ------------------------------------------------------------------

    def decrypt_database(self, crypt_file: str, encryption_key: str) -> dict[str, Any]:
        try:
            from wa_crypt_tools.lib.db.dbfactory import DatabaseFactory
            from wa_crypt_tools.lib.key.keyfactory import KeyFactory

            crypt_path = Path(crypt_file)
            decrypted_path = crypt_path.parent / "msgstore.db"

            key_str = encryption_key.replace(" ", "").strip()
            if len(key_str) != 64:
                return {"success": False, "error": "Encryption key must be exactly 64 characters"}

            key = KeyFactory.from_hex(key_str)
            with open(crypt_path, "rb") as f:
                db = DatabaseFactory.from_file(f)
            with open(crypt_path, "rb") as f:
                decrypted_data = db.decrypt(key, f.read())

            with open(decrypted_path, "wb") as f:
                f.write(decrypted_data)

            return {"success": True, "decrypted_path": str(decrypted_path)}
        except ImportError as e:
            return {"success": False, "error": f"wa-crypt-tools is not installed: {e}"}
        except ValueError as e:
            return {"success": False, "error": f"Invalid encryption key: {e}"}
        except FileNotFoundError as e:
            return {"success": False, "error": f"File not found: {e}"}
        except Exception as e:  # noqa: BLE001
            self.last_error = traceback.format_exc()
            return {"success": False, "error": f"Decryption failed: {type(e).__name__}: {e}"}

    # ------------------------------------------------------------------
    # Organize
    # ------------------------------------------------------------------

    def start_organization(
        self,
        db_path: str,
        media_path: str,
        output_path: str,
        contacts_path: str | None = None,
    ) -> dict[str, Any]:
        self.running = True
        self.processed_files = 0
        self.total_files = 0
        self.last_error = None
        threading.Thread(
            target=self._run_organize,
            args=(db_path, media_path, output_path, contacts_path),
            daemon=True,
        ).start()
        return {"success": True}

    def _run_organize(
        self, db_path: str, media_path: str, output_path: str, contacts_path: str | None
    ) -> None:
        def emit(kind: str, **data: Any) -> None:
            if kind == "progress":
                self.processed_files = data.get("current", 0)
                self.total_files = data.get("total", 0)
            self._emit(f"organize:{kind}", **data)

        try:
            contacts = load_vcf_contacts(Path(contacts_path)) if contacts_path else None
            Organizer(
                db_path=Path(db_path),
                media_dir=Path(media_path),
                out_dir=Path(output_path),
                contacts=contacts,
                on_progress=lambda current, total: emit(
                    "progress", current=current, total=total
                ),
            ).run()
            if self.running:
                self._emit("organize:complete", path=output_path)
            else:
                self._emit("organize:canceled")
        except Exception as e:  # noqa: BLE001
            self.last_error = traceback.format_exc()
            self._emit("organize:error", message=str(e))
        finally:
            self.running = False

    def cancel_organization(self) -> dict[str, Any]:
        self.running = False
        return {"success": True}

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def export_diagnostics(self) -> dict[str, Any]:
        try:
            info = [
                "wa-sort-media diagnostics",
                f"time: {datetime.now().isoformat(timespec='seconds')}",
                f"platform: {sys.platform}",
                f"python: {sys.version.splitlines()[0]}",
                f"frozen: {getattr(sys, 'frozen', False)}",
                f"adb: {shutil.which('adb') or 'not found'}",
                f"running: {self.running}",
                f"progress: {self.processed_files}/{self.total_files}",
                "",
                "last error:",
                self.last_error or "(none)",
            ]
            out = Path(tempfile.gettempdir()) / "wa-sort-media-diagnostics.txt"
            out.write_text("\n".join(info), encoding="utf-8")
            return {"success": True, "path": str(out)}
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": str(e)}
