from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from contextlib import closing

from .datatypes import Chat, DmChat, GroupChat


def match_files_to_chats(db_path: Path) -> dict[str, Chat]:
    """Return a mapping from filename to the chat that originated it."""

    if not db_path.exists():
        raise FileNotFoundError(f"msgstore.db not found: {db_path}")

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT
                    media.file_path,
                    jid.user,
                    jid.server,
                    chat.subject
                FROM message_media media
                    JOIN message ON media.message_row_id = message._id
                    JOIN chat ON message.chat_row_id = chat._id
                    JOIN jid ON chat.jid_row_id = jid._id
                WHERE media.file_path IS NOT NULL
            """)
        except sqlite3.OperationalError as e:
            raise ValueError("Invalid WhatsApp database.") from e

        mapping: dict[str, Chat] = {}
        for row in cur:
            basename = os.path.basename(row["file_path"])
            user = row["user"]
            server = row["server"]

            chat: Chat
            match server:
                case "g.us":
                    chat = GroupChat(
                        group_id=user,
                        subject=row["subject"],
                    )
                case "s.whatsapp.net":
                    chat = DmChat(
                        user_id=user,
                    )
                case "broadcast":
                    continue

            mapping.setdefault(basename, chat)

    return mapping
