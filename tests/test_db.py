"""Tests for the db module."""

from pathlib import Path

import pytest

from src.db import match_files_to_chats
from src.datatypes import DmChat, GroupChat


class TestMatchFilesToChats:
    def test_db_chat(self, db: Path):
        mapping = match_files_to_chats(db)
        dm_chat = mapping.get("IMG-20240101-WA0001.jpg")
        assert isinstance(dm_chat, DmChat)
        assert dm_chat.user_id == "15559999999"

    def test_group_chat_with_subject(self, db: Path):
        mapping = match_files_to_chats(db)
        group_chat = mapping.get("VID-20240101-WA0002.mp4")
        assert isinstance(group_chat, GroupChat)
        assert group_chat.group_id == "15559999999-12345678"
        assert group_chat.subject == "Group Name"

    def test_group_chat_without_subject(self, db: Path):
        mapping = match_files_to_chats(db)
        group_chat = mapping.get("AUD-20240101-WA0003.opus")
        assert isinstance(group_chat, GroupChat)
        assert group_chat.group_id == "15558888888-12345678"
        assert group_chat.subject is None

    def test_broadcast_message_skipped(self, db: Path):
        mapping = match_files_to_chats(db)
        assert len(mapping) == 3

    def test_missing_file(self, tmp_path: Path):
        non_existent = tmp_path / "nonexistent.db"
        with pytest.raises(FileNotFoundError):
            match_files_to_chats(non_existent)

    def test_missing_tables(self, db_missing_tables: Path):
        with pytest.raises(ValueError):
            match_files_to_chats(db_missing_tables)
