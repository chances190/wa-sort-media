import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a minimal msgstore.db with known data."""
    db_path = tmp_path / "msgstore.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE jid (_id INTEGER PRIMARY KEY, user TEXT, server TEXT);
        CREATE TABLE chat (_id INTEGER PRIMARY KEY, jid_row_id INTEGER, subject TEXT);
        CREATE TABLE message (_id INTEGER PRIMARY KEY, chat_row_id INTEGER);
        CREATE TABLE message_media (
            message_row_id INTEGER,
            file_path TEXT,
            file_size INTEGER,
            file_hash TEXT
        );

        -- Direct chat: +5511999999999
        INSERT INTO jid VALUES (1, '5511999999999', 's.whatsapp.net');
        INSERT INTO chat VALUES (1, 1, NULL);
        INSERT INTO message VALUES (1, 1);
        INSERT INTO message_media VALUES (1, 'WhatsApp Images/IMG-20240101-WA0001.jpg', 12345, NULL);

        -- Group chat: Family Group (with subject)
        INSERT INTO jid VALUES (2, '123456789', 'g.us');
        INSERT INTO chat VALUES (2, 2, 'Family Group');
        INSERT INTO message VALUES (2, 2);
        INSERT INTO message_media VALUES (2, 'WhatsApp Video/VID-20240101-WA0002.mp4', 67890, NULL);

        -- Group chat: no subject (fallback to group_<id>)
        INSERT INTO jid VALUES (3, '987654321', 'g.us');
        INSERT INTO chat VALUES (3, 3, NULL);
        INSERT INTO message VALUES (3, 3);
        INSERT INTO message_media VALUES (3, 'WhatsApp Images/IMG-20240101-WA0003.jpg', 11111, NULL);
        """
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def test_media_dir(tmp_path: Path) -> Path:
    """Create a minimal WhatsApp Media directory structure."""
    media = tmp_path / "WhatsApp Media"
    (media / "WhatsApp Images").mkdir(parents=True)
    (media / "WhatsApp Video").mkdir(parents=True)

    (media / "WhatsApp Images" / "IMG-20240101-WA0001.jpg").touch()
    (media / "WhatsApp Video" / "VID-20240101-WA0002.mp4").touch()
    (media / "WhatsApp Images" / "IMG-20240101-WA0003.jpg").touch()
    (media / "WhatsApp Video" / "unmatched-file.mp4").touch()

    return media


@pytest.fixture
def test_contacts() -> dict[str, str]:
    return {"5511999999999": "Mom"}