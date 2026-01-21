"""Backup API module - handles device detection, backup execution, and monitoring."""

import sys
import json
import threading
import subprocess
from pathlib import Path
from datetime import datetime
import warnings
from tkinter import filedialog, Tk
from typing import Any

warnings.filterwarnings("ignore")


def get_base_path():
    """Get the base path for bundled resources."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        return Path(sys._MEIPASS)

    return Path(__file__).resolve().parent.parent


class BackupAPI:
    """API class exposed to JavaScript"""

    def __init__(self):
        self._window = None
        self.backup_task = None
        self.running = False
        self.total_files = 0
        self.processed_files = 0

    def set_window(self, window: Any) -> None:
        """Set reference to webview window"""
        self._window = window

    def decrypt_database(self, crypt_file: str, encryption_key: str) -> dict[str, Any]:
        """Decrypt WhatsApp database using wa-crypt-tools library"""
        try:
            from pathlib import Path
            from wa_crypt_tools.lib.key.keyfactory import KeyFactory
            from wa_crypt_tools.lib.db.dbfactory import DatabaseFactory
            import zlib

            crypt_path = Path(crypt_file)
            decrypted_path = crypt_path.parent / "msgstore.db"

            # Clean the encryption key (remove spaces)
            key_str = encryption_key.replace(" ", "").strip()

            if len(key_str) != 64:
                return {"success": False, "error": "Encryption key must be exactly 64 characters"}

            # Create key from the 64-digit hex string
            key = KeyFactory.from_hex(key_str)

            # Load the encrypted database
            with open(crypt_path, "rb") as f:
                db = DatabaseFactory.from_file(f)

            # Read encrypted data and decrypt
            with open(crypt_path, "rb") as f:
                encrypted_data = f.read()
                decrypted_data = db.decrypt(key, encrypted_data)

            # Write decrypted data
            with open(decrypted_path, "wb") as f:
                f.write(decrypted_data)

            return {
                "success": True,
                "decrypted_path": str(decrypted_path),
            }
        except ImportError as e:
            return {
                "success": False,
                "error": f"Import error: {str(e)}. Make sure wa-crypt-tools is installed in the current environment.",
            }
        except ValueError as e:
            return {"success": False, "error": f"Invalid encryption key: {str(e)}"}
        except FileNotFoundError as e:
            return {"success": False, "error": f"File not found: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Decryption failed: {type(e).__name__}: {str(e)}"}

    def get_devices(self):
        """Get list of connected MTP devices"""
        try:
            scripts_dir = get_base_path() / "scripts"
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(scripts_dir / "Get-MTPDevices.ps1"),
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            devices = [line.strip() for line in result.stdout.split("\n") if line.strip()]
            return {"success": True, "devices": devices}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def start_backup(self, device: str, destination: str) -> dict[str, Any]:
        """Start backup task"""
        try:
            backup_folder = Path(destination)
            backup_folder.mkdir(parents=True, exist_ok=True)

            self.running = True
            self.processed_files = 0
            self.total_files = 0

            scripts_dir = get_base_path() / "scripts"
            self.backup_task = subprocess.Popen(
                [
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(scripts_dir / "MTP-Copy.ps1"),
                    "-deviceName",
                    device,
                    "-destinationPath",
                    str(backup_folder),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            # Monitor backup in separate thread
            threading.Thread(target=self._monitor_backup, daemon=True).start()
            return {"success": True, "backup_path": str(backup_folder)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _monitor_backup(self):
        """Monitor backup progress"""
        import time

        while self.running and self.backup_task and self.backup_task.poll() is None:
            if self.backup_task.stdout:
                line = self.backup_task.stdout.readline()
                if line:
                    line = line.strip()

                    # Parse progress markers from PowerShell script
                    if "[PROGRESS]" in line:
                        try:
                            # Extract progress info: [PROGRESS] current/total
                            progress_part = line.split("[PROGRESS]")[1].strip()
                            if "/" in progress_part:
                                parts = progress_part.split("/")
                                current = int(parts[0].strip())
                                total = int(parts[1].strip())
                                self.processed_files = current
                                self.total_files = total
                                percentage = (current / max(total, 1)) * 100
                            else:
                                percentage = 0
                        except (ValueError, IndexError):
                            percentage = 0

                        if self._window:
                            # Extract just the numbers for display
                            display_msg = f"[PROGRESS] {self.processed_files}/{self.total_files}"
                            self._window.evaluate_js(
                                f"window.updateProgress({json.dumps(display_msg)}, {percentage:.0f})"
                            )
                    else:
                        # Log messages (counting phase, folder messages, etc)
                        if self._window:
                            self._window.evaluate_js(
                                f"window.updateProgress({json.dumps(line)}, 0)"
                            )
            time.sleep(0.1)

        if self.running and self._window:
            self._window.evaluate_js("window.backupComplete()")
        elif not self.running and self._window:
            self._window.evaluate_js("window.backupCanceled()")

    def cancel_backup(self):
        """Cancel backup task"""
        self.running = False
        if self.backup_task:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(self.backup_task.pid)],
                capture_output=True,
            )
            return {"success": True}
        return {"success": False, "error": "No backup in progress"}

    def pick_folder(self):
        """Open folder picker dialog"""
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        try:
            path = filedialog.askdirectory(
                title="Select Folder", initialdir=str(Path.home() / "Documents")
            )
            return {"success": True, "path": path} if path else {"success": False, "path": None}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            root.destroy()

    def pick_file(self):
        """Open file picker dialog"""
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        try:
            path = filedialog.askopenfilename(
                title="Select Database File",
                initialdir=str(Path.home() / "Documents"),
                filetypes=[("Database files", "*.db.crypt15 *.db"), ("All files", "*.*")],
            )
            return {"success": True, "path": path} if path else {"success": False, "path": None}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            root.destroy()

    def start_organization(
        self, db_path: str, media_path: str, output_path: str, contacts_path: str | None = None
    ) -> dict[str, Any]:
        """Start media organization task using actual wasort organizer"""
        try:
            self.running = True
            self.processed_files = 0
            self.total_files = 0

            # Start organization in a separate thread
            threading.Thread(
                target=self._organize_with_wasort,
                args=(db_path, media_path, output_path, contacts_path),
                daemon=True,
            ).start()

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _organize_with_wasort(
        self, db_path: str, media_path: str, output_path: str, contacts_path: str | None = None
    ) -> None:
        """Run the actual wasort organizer"""
        from src.organizer import organize_files

        try:
            db = Path(db_path)
            media = Path(media_path)
            output = Path(output_path)
            contacts = Path(contacts_path) if contacts_path else None

            # Notify start
            if self._window:
                self._window.evaluate_js(
                    "window.updateOrganizerProgress('[LOG] Starting organization...', 0)"
                )

            # Count total files first
            from src.organizer import scan_files

            all_files, cat_totals = scan_files(media)
            self.total_files = sum(cat_totals.values())

            if self._window:
                self._window.evaluate_js(
                    f"window.updateOrganizerProgress('[LOG] Found {self.total_files} files to organize', 0)"
                )

            # Create custom progress callback
            class ProgressTracker:
                def __init__(self, api_ref):
                    self.api = api_ref
                    self.count = 0

                def update(self, cat, done_count):
                    self.count = done_count
                    pct = (self.count / max(self.api.total_files, 1)) * 100
                    if self.api._window:
                        self.api._window.evaluate_js(
                            f"window.updateOrganizerProgress('[PROGRESS] {self.count}/{self.api.total_files}', {pct:.0f})"
                        )

            # Run organization (dry_run=False, do_move=False means copy)
            organize_files(
                db_path=db,
                media_root=media,
                out_root=output,
                dry_run=False,
                do_move=False,
                verbose=False,
                tui=None,  # Use None instead of custom tracker due to type mismatch
            )

            if self.running and self._window:
                self._window.evaluate_js("window.organizerComplete()")
            elif not self.running and self._window:
                self._window.evaluate_js("window.organizerCanceled()")

        except Exception as e:
            if self._window:
                self._window.evaluate_js(f"window.updateOrganizerProgress('[ERROR] {str(e)}', 0)")
                self._window.evaluate_js("window.organizerCanceled()")

        self.running = False

    def cancel_organization(self):
        """Cancel organization task"""
        self.running = False
        return {"success": True}
