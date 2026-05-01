"""Organizer: move/copy media files into conversation folders."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .datatypes import ChatMatch, GroupMatch, MediaType
from .db import match_filename_to_chat
from .utils import sanitize_dir_name


logger = logging.getLogger(__name__)


def organize(
    db_path: Path,
    media_dir: Path,
    out_dir: Path,
    contacts: dict[str, str] | None = None,
    *,
    dry_run: bool = False,
    copy: bool = True,
) -> int:
    """Organize media files into out_dir/<chat_name>/<category>/<file>.

    Returns the number of files processed.
    """
    logger.debug("Building media map from database: %s", db_path)
    media_map = match_filename_to_chat(db_path)
    files = _categorize_files(media_dir)
    logger.debug("Discovered %s files under media directory", len(files))

    if not files:
        logger.info("No media files found.")
        return 0

    processed = 0
    unmatched = 0
    total = len(files)

    for src, media_type in files:
        dest = _resolve_dest(src, out_dir, media_type, media_map, contacts)
        if dest.parent == "Unmatched":
            unmatched += 1

        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if copy:
                logger.debug("Copying %s -> %s", src.name, dest)
                shutil.copy2(src, dest)
            else:
                logger.debug("Moving %s -> %s", src.name, dest)
                shutil.move(src, dest)

        processed += 1
        if processed % 100 == 0:
            logger.info("%s/%s files processed...", processed, total)

    if unmatched:
        logger.info("Skipped %s unmatched files.", unmatched)

    logger.debug("Finished organizing files. Processed=%s, Unmatched=%s", processed, unmatched)
    return processed


def _categorize_files(media_root: Path) -> list[tuple[Path, MediaType]]:
    results: list[tuple[Path, MediaType]] = []
    for src in media_root.rglob("*"):
        if src.is_file():
            results.append((src, MediaType.from_path(src, media_root)))
    return results


def _resolve_dest(
    src: Path,
    out_dir: Path,
    media_type: MediaType,
    media_map: dict[str, list[ChatMatch | GroupMatch]],
    contacts: dict[str, str] | None,
) -> Path:
    matches = media_map.get(src.name)

    if not matches:
        logger.debug("No DB match for %s", src.name, src.name)
        return out_dir / "Unmatched" / src.name

    if len(matches) > 1:
        logger.debug("Multiple DB matches for %s (%s); using first match", src.name, len(matches))

    match = matches[0]

    chat: str
    if isinstance(match, GroupMatch):
        chat = _get_group_name(match)
        logger.debug(
            "Matched %s (group %r jid=%s)",
            src.name,
            match.jid_user,
            match.subject,
        )
    else:
        chat = _get_chat_name(match, contacts)
        logger.debug("Matched %s (chat %r jid=%s)", src.name, match.jid_user, chat)

    return out_dir / sanitize_dir_name(chat) / media_type.value / src.name


def _get_chat_name(match: ChatMatch, contacts: dict[str, str] | None) -> str:
    user = match.jid_user

    if contacts and user in contacts:
        return contacts[user]
    return f"+{user}"


def _get_group_name(match: GroupMatch) -> str:
    if match.subject:
        return match.subject
    return f"group_{match.jid_user}"
