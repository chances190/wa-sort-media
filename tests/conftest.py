"""Test fixtures for WhatsApp Media Organizer."""

from pathlib import Path

import pytest
import sqlite3

from src.db import match_files_to_chats
from src.contacts import load_vcf_contacts
from src.datatypes import Chat, Contacts

# === Contacts ================================================================


@pytest.fixture
def wa_db(tmp_path: Path) -> Path:
    path = tmp_path / "wa.db"
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE wa_contacts (
            jid TEXT PRIMARY KEY,
            display_name TEXT,
            wa_name TEXT,
            given_name TEXT,
            family_name TEXT
        );
        
        INSERT INTO wa_contacts (jid, display_name, wa_name) 
        VALUES ('15559999999@s.whatsapp.net', 'John Doe', 'JohnDoeUsername');
        
        INSERT INTO wa_contacts (jid, display_name, wa_name) 
        VALUES ('15558888888@s.whatsapp.net', NULL, 'JaneDoeUsername');
        
        INSERT INTO wa_contacts (jid, display_name, wa_name) 
        VALUES ('15557777777@s.whatsapp.net', NULL, NULL);
    """)

    conn.commit()
    conn.close()
    return path


@pytest.fixture
def wa_db_without_contacts(tmp_path: Path) -> Path:
    path = tmp_path / "no_contacts_wa.db"
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE other_table (id INTEGER PRIMARY KEY);
        INSERT INTO other_table (id) VALUES (1);
    """)

    conn.commit()
    conn.close()
    return path


@pytest.fixture
def vcf_file(tmp_path: Path) -> Path:
    path = tmp_path / "contacts.vcf"
    content = """BEGIN:VCARD
VERSION:3.0
FN:John Doe
TEL;TYPE=CELL:+15559999999
END:VCARD
BEGIN:VCARD
VERSION:3.0
FN:Jane Doe
TEL;TYPE=CELL:+15558888888
TEL;TYPE=WORK:+15557777777
END:VCARD
BEGIN:VCARD
VERSION:3.0
FN:Quoted Printable
FN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:=4A=6F=68=6E=20=53=6D=69=74=68
TEL;TYPE=CELL:+15556666666
END:VCARD
"""
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def contacts(vcf_file: Path) -> Contacts:
    return load_vcf_contacts(vcf_file)


# === db ======================================================================


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "msgstore.db"
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE jid (
            _id INTEGER PRIMARY KEY,
            user TEXT NOT NULL,
            server TEXT NOT NULL
        );
        
        CREATE TABLE chat (
            _id INTEGER PRIMARY KEY,
            jid_row_id INTEGER NOT NULL,
            subject TEXT,
            FOREIGN KEY (jid_row_id) REFERENCES jid(_id)
        );
        
        CREATE TABLE message (
            _id INTEGER PRIMARY KEY,
            chat_row_id INTEGER NOT NULL,
            FOREIGN KEY (chat_row_id) REFERENCES chat(_id)
        );
        
        CREATE TABLE message_media (
            message_row_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            file_hash TEXT,
            FOREIGN KEY (message_row_id) REFERENCES message(_id)
        );
        
        -- Direct chat: +15551234567
        INSERT INTO jid (_id, user, server) VALUES (1, '15559999999', 's.whatsapp.net');
        INSERT INTO chat (_id, jid_row_id, subject) VALUES (1, 1, NULL);
        INSERT INTO message (_id, chat_row_id) VALUES (1, 1);
        INSERT INTO message_media (message_row_id, file_path, file_size) 
        VALUES (1, 'WhatsApp Images/IMG-20240101-WA0001.jpg', 102400);
        
        -- Group chat (with subject)
        INSERT INTO jid (_id, user, server) VALUES (2, '15559999999-12345678', 'g.us');
        INSERT INTO chat (_id, jid_row_id, subject) VALUES (2, 2, 'Group Name');
        INSERT INTO message (_id, chat_row_id) VALUES (2, 2);
        INSERT INTO message_media (message_row_id, file_path, file_size) 
        VALUES (2, 'WhatsApp Videos/VID-20240101-WA0002.mp4', 102400);
        
        -- Group chat (no subject)
        INSERT INTO jid (_id, user, server) VALUES (3, '15558888888-12345678', 'g.us');
        INSERT INTO chat (_id, jid_row_id, subject) VALUES (3, 3, NULL);
        INSERT INTO message (_id, chat_row_id) VALUES (3, 3);
        INSERT INTO message_media (message_row_id, file_path, file_size) 
        VALUES (3, 'WhatsApp Audios/AUD-20240101-WA0003.opus', 102400);
        
        -- Broadcast message (should be skipped)
        INSERT INTO jid (_id, user, server) VALUES (4, 'status', 'broadcast');
        INSERT INTO chat (_id, jid_row_id, subject) VALUES (4, 4, 'Broadcast');
        INSERT INTO message (_id, chat_row_id) VALUES (4, 4);
        INSERT INTO message_media (message_row_id, file_path, file_size) 
        VALUES (4, 'WhatsApp Documents/DOC-20240101-WA0004.pdf', 102400);
    """)

    conn.commit()
    conn.close()
    return path


@pytest.fixture
def db_missing_tables(tmp_path: Path) -> Path:
    path = tmp_path / "missing_msgstore.db"
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE other_table (id INTEGER PRIMARY KEY);
        INSERT INTO other_table (id) VALUES (1);
    """)

    conn.commit()
    conn.close()
    return path


@pytest.fixture
def chat_map(db: Path) -> dict[str, Chat]:
    return match_files_to_chats(db)


# === Organizer ===============================================================


@pytest.fixture
def media_dir(tmp_path: Path) -> Path:
    media = tmp_path / "WhatsApp Media"
    (media / "WhatsApp Images").mkdir(parents=True)
    (media / "WhatsApp Video").mkdir(parents=True)
    (media / "WhatsApp Audio").mkdir(parents=True)
    (media / "WhatsApp Documents").mkdir(parents=True)
    (media / "WhatsApp Animated Gifs").mkdir(parents=True)
    (media / "WhatsApp Stickers").mkdir(parents=True)
    (media / "WhatsApp Video Notes").mkdir(parents=True)
    (media / "WhatsApp Voice Notes").mkdir(parents=True)

    (media / "WhatsApp Images" / "IMG-20240101-WA0001.jpg").touch()
    (media / "WhatsApp Video" / "VID-20240101-WA0002.mp4").touch()
    (media / "WhatsApp Audio" / "AUD-20240101-WA0004.opus").touch()
    (media / "WhatsApp Documents" / "DOC-20240101-WA0005.pdf").touch()

    # File in a subdirectory
    (media / "WhatsApp Images" / "Sent").mkdir(parents=True, exist_ok=True)
    (media / "WhatsApp Images" / "Sent" / "IMG-20240101-WA0006.jpg").touch()

    # Hidden file (should be ignored)
    (media / "WhatsApp Images" / ".hidden.jpg").touch()

    # File without a corresponding chat
    (media / "WhatsApp Images" / "unmatched-file.png").touch()

    return media


@pytest.fixture
def organizer_default_args(db: Path, media_dir: Path) -> dict:
    return {
        "db_path": db,
        "media_dir": media_dir,
        "out_dir": media_dir.parent / "organized",
        "contacts": None,
        "dry_run": False,
        "copy": True,
    }
