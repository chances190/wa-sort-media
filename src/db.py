from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from contextlib import closing

from .datatypes import ChatMatch, GroupMatch


def match_filename_to_chat(db_path: Path) -> dict[str, list[ChatMatch | GroupMatch]]:
    """Return a mapping from filename to the chat that originated it."""

    if not db_path.exists():
        raise FileNotFoundError(f"msgstore.db not found: {db_path}")

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                mm.message_row_id,
                mm.file_path,
                j.user,
                j.server,
                c.subject
            FROM message_media mm
            JOIN message m ON mm.message_row_id = m._id
            JOIN chat c ON m.chat_row_id = c._id
            JOIN jid j ON c.jid_row_id = j._id
            WHERE mm.file_path IS NOT NULL
        """
        )

        mapping: dict[str, list[ChatMatch | GroupMatch]] = {}
        for row in cur.fetchall():
            file_path = row["file_path"]
            if not file_path:
                continue

            basename = os.path.basename(file_path)
            user = row["user"]
            server = row["server"]

            match: ChatMatch | GroupMatch
            if server and server.lower() == "g.us":
                match = GroupMatch(
                    jid_user=user,
                    subject=row["subject"],
                )
            else:
                match = ChatMatch(
                    jid_user=user,
                )

            mapping.setdefault(basename, []).append(match)

    return mapping
