"""DB helpers: build mapping from message_media and resolve chat names."""

from __future__ import annotations

import sqlite3
import os
from pathlib import Path
from contextlib import closing

from .utils import sanitize_dir_name


def build_db_map(
    db_path: Path,
) -> dict[str, list[tuple[int, int | None, str | None, int | None, str | None]]]:
    """Return a mapping from basename -> list of tuples:
    (message_row_id, chat_row_id, file_path, file_size, file_hash)
    """
    mapping: dict[str, list[tuple[int, int | None, str | None, int | None, str | None]]] = {}

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            """
            SELECT mm.message_row_id, m.chat_row_id, mm.file_path, mm.file_size, mm.file_hash
            FROM message_media mm
            LEFT JOIN message m ON mm.message_row_id = m._id
            WHERE mm.file_path IS NOT NULL
            """
        )

        for row in cur.fetchall():
            file_path = row["file_path"]
            if not file_path:
                continue
            basename = os.path.basename(file_path)
            mapping.setdefault(basename, []).append(
                (
                    row["message_row_id"],
                    row["chat_row_id"],
                    row["file_path"],
                    row["file_size"],
                    row["file_hash"],
                )
            )

    return mapping


def lookup_chat_name(
    db_path: Path,
    chat_row_id: int,
    contacts_map: dict[str, str] | None = None,
    verbose: bool = False,
) -> str:
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT subject, jid_row_id FROM chat WHERE _id = ?", (chat_row_id,))
        r = cur.fetchone()
        if not r or not r["jid_row_id"]:
            return sanitize_dir_name(f"chat_{chat_row_id}")

        subject = r["subject"]
        jid_row_id = r["jid_row_id"]

        cur.execute("SELECT user, server FROM jid WHERE _id = ?", (jid_row_id,))
        j = cur.fetchone()
        if not j:
            return sanitize_dir_name(f"jid_{jid_row_id}")

        user = j["user"]
        server = j["server"]

        # Group chat: use subject if available
        if server and server.lower() == "g.us":
            return sanitize_dir_name(subject or f"group_jid_{jid_row_id}")

        # Person: try contacts_map first, then numeric phone
        if user and user.isdigit():
            if contacts_map and user in contacts_map:
                if verbose:
                    print(f"Resolved +{user} -> {contacts_map[user]}")
                return sanitize_dir_name(contacts_map[user])
            return sanitize_dir_name(f"+{user}")

        return sanitize_dir_name(f"jid_{jid_row_id}")
