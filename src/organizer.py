"""Organizer: move/copy media files into conversation folders."""

from __future__ import annotations
from src.contacts import PhoneNumber

import logging
import re
import shutil
from pathlib import Path

from .datatypes import Chat, DmChat, GroupChat, MediaType, Contacts
from .db import match_files_to_chats


logger = logging.getLogger(__name__)


class Organizer:
    """Organize media files into out_dir/<chat_name>/<category>/<file>."""

    def __init__(
        self,
        db_path: Path,
        media_dir: Path,
        out_dir: Path,
        *,
        contacts: Contacts | None = None,
        dry_run: bool = False,
        copy: bool = True,
    ):
        self.db_path = db_path.resolve()
        self.media_dir = media_dir.resolve()
        self.out_dir = out_dir.resolve()
        self.contacts = contacts
        self.dry_run = dry_run
        self.copy = copy

        self.processed = 0
        self.unmatched = 0

    def run(self) -> None:
        logger.debug("Building media map from database: %s", self.db_path)
        chat_map = match_files_to_chats(self.db_path)
        files = self._get_categorized_files()
        logger.debug("Discovered %s files under media directory", len(files))

        if not files:
            logger.info("No media files found.")
            return

        total = len(files)
        for file in files:
            src = file[0]
            dest = self.out_dir / self._resolve_folder_name(file, chat_map)

            if not self.dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                if self.copy:
                    logger.debug("Copying %s -> %s", src.name, dest)
                    shutil.copy2(src, dest)
                else:
                    logger.debug("Moving %s -> %s", src.name, dest)
                    shutil.move(src, dest)

            self.processed += 1
            logger.info("%s/%s files processed...", self.processed, total)

        logger.info("Done. %s files organized into %s/", self.processed, self.out_dir)
        logger.info("Couldn't find a match for %s files.", self.processed, self.out_dir)

    def _get_categorized_files(self) -> list[tuple[Path, MediaType]]:
        results: list[tuple[Path, MediaType]] = []
        for src in self.media_dir.rglob("*"):
            if src.is_file() and not src.name.startswith("."):
                results.append((src, MediaType.from_path(src, self.media_dir)))

        results.sort(key=(lambda item: item[0]))
        return results

    def _resolve_folder_name(
        self,
        file: tuple[Path, MediaType],
        chat_map: dict[str, Chat],
    ) -> Path:
        filename = file[0].name
        media_type = file[1].value
        chat = chat_map.get(filename)

        dir_name: str
        match chat:
            case GroupChat():
                if chat.subject:
                    dir_name = chat.subject
                else:
                    dir_name = f"Group {chat.group_id}"
                logger.debug(f"Matched {filename} -> {dir_name} (group_id={chat.group_id})")

            case DmChat():
                if self.contacts and PhoneNumber(chat.user_id) in self.contacts:
                    dir_name = self.contacts[chat.user_id]
                else:
                    dir_name = f"+{chat.user_id}"
                logger.debug(f"Matched {filename} -> {dir_name} (chat_id={chat.user_id})")

            case None:
                dir_name = "Unmatched"
                self.unmatched += 1
                logger.debug("No chat match for %s", filename)

        return Path() / self._sanitize_dir_name(dir_name) / media_type / filename

    def _sanitize_dir_name(self, name: str) -> str:
        windows_illegal_chars = r'[<>:"/\\|?*\x00-\x1F]'
        windows_reserved_names = r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$"

        name = re.sub(windows_illegal_chars, "_", name)

        name = name.rstrip(". ")  # Strip trailing dots and spaces (forbidden in Windows)

        if re.match(windows_reserved_names, name, re.IGNORECASE) or name.startswith((".", "-")):
            name = f"_{name}"

        return name[:255]
