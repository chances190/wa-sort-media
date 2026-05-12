"""Tests for the organizer module."""

import re

from pathlib import Path

import pytest

from src.organizer import Organizer
from src.datatypes import GroupChat, MediaType, ChatId, Contacts, Chat


@pytest.fixture
def organizer(organizer_default_args: dict):
    return Organizer(**organizer_default_args)


class TestOrganizerInit:
    def test_defaults(self):
        organizer = Organizer(Path("db"), Path("media"), Path("out"))
        assert organizer.db_path == Path("db").resolve()
        assert organizer.media_dir == Path("media").resolve()
        assert organizer.out_dir == Path("out").resolve()
        assert organizer.contacts is None
        assert organizer.dry_run is False
        assert organizer.copy is True
        assert organizer.processed == 0
        assert organizer.unmatched == 0


class TestOrganizerGetCategorizedFiles:
    def test_collects_and_categorizes(self, organizer_default_args: dict):
        organizer = Organizer(**organizer_default_args)
        files = organizer._get_categorized_files()
        assert len(files) == 6
        for file_path, media_type in files:
            assert file_path.exists() and isinstance(media_type, MediaType)

    def test_empty_directory(self, tmp_path: Path, organizer_default_args: dict):
        organizer_default_args["media_dir"] = tmp_path / "empty"
        organizer_default_args["media_dir"].mkdir()
        files = Organizer(**organizer_default_args)._get_categorized_files()
        assert len(files) == 0

    def test_ignores_hidden_files(self, tmp_path: Path, organizer_default_args: dict):
        media_dir = tmp_path / "media"
        images_dir = media_dir / "WhatsApp Images"
        images_dir.mkdir(parents=True)
        (images_dir / ".hidden.jpg").touch()
        (images_dir / "visible.jpg").touch()
        organizer_default_args["media_dir"] = media_dir
        files = Organizer(**organizer_default_args)._get_categorized_files()
        assert len(files) == 1 and files[0][0].name == "visible.jpg"

    def test_sorts_by_path(self, tmp_path: Path, organizer_default_args: dict):
        media_dir = tmp_path / "media"
        images_dir = media_dir / "WhatsApp Images"
        images_dir.mkdir(parents=True)
        for name in ["z.jpg", "a.jpg", "m.jpg"]:
            (images_dir / name).touch()
        organizer_default_args["media_dir"] = media_dir
        files = Organizer(**organizer_default_args)._get_categorized_files()
        assert [f[0].name for f in files] == ["a.jpg", "m.jpg", "z.jpg"]


class TestOrganizerSanitizeDirName:
    @pytest.fixture
    def organizer(self, organizer_default_args: dict):
        return Organizer(**organizer_default_args)

    def test_allows_normal_names(self, organizer: Organizer):
        assert organizer._sanitize_dir_name("Normal Name") == "Normal Name"
        assert organizer._sanitize_dir_name("Name-with-dashes") == "Name-with-dashes"

    def test_replaces_illegal_chars(self, organizer: Organizer):
        assert organizer._sanitize_dir_name("File<>:|?*name") == "File______name"
        assert organizer._sanitize_dir_name('File"name') == "File_name"

    def test_prefixes_reserved_names(self, organizer: Organizer):
        assert organizer._sanitize_dir_name("CON") == "_CON"
        assert organizer._sanitize_dir_name("COM1") == "_COM1"
        assert organizer._sanitize_dir_name("COM10") == "COM10"

    def test_strips_trailing_dots_spaces(self, organizer: Organizer):
        assert organizer._sanitize_dir_name("Name.") == "Name"
        assert organizer._sanitize_dir_name("Name  ") == "Name"

    def test_prefixes_leading_dot_or_dash(self, organizer: Organizer):
        assert organizer._sanitize_dir_name(".hidden") == "_.hidden"
        assert organizer._sanitize_dir_name("-start") == "_-start"

    def test_truncates_to_255_chars(self, organizer: Organizer):
        result = organizer._sanitize_dir_name("A" * 300)
        assert len(result) == 255


class TestOrganizerResolveFolderName:
    @pytest.fixture
    def organizer(self, organizer_default_args: dict):
        return Organizer(**organizer_default_args)

    def test_dm_uses_contact_name(
        self, organizer: Organizer, contacts: Contacts, chat_map: dict[str, Chat]
    ):
        organizer.contacts = contacts
        file = (
            organizer.media_dir / "WhatsApp Images" / "IMG-20240101-WA0001.jpg",
            MediaType.IMAGES,
        )
        result = organizer._resolve_folder_name(file, chat_map)
        assert result == Path("John Doe/Images/IMG-20240101-WA0001.jpg")

    def test_dm_uses_phone_without_contact(self, organizer: Organizer, chat_map: dict[str, Chat]):
        file = (
            organizer.media_dir / "WhatsApp Images" / "IMG-20240101-WA0001.jpg",
            MediaType.IMAGES,
        )
        result = organizer._resolve_folder_name(file, chat_map)
        assert result == Path("+15559999999/Images/IMG-20240101-WA0001.jpg")

    def test_group_uses_subject(self, organizer: Organizer, chat_map: dict[str, Chat]):
        file = (
            organizer.media_dir / "WhatsApp Video" / "VID-20240101-WA0002.mp4",
            MediaType.VIDEO,
        )
        result = organizer._resolve_folder_name(file, chat_map)
        assert result == Path("Group Name/Video/VID-20240101-WA0002.mp4")

    def test_group_uses_id_without_subject(self, organizer: Organizer, chat_map: dict[str, Chat]):
        file = (
            organizer.media_dir / "WhatsApp Audio" / "AUD-20240101-WA0003.opus",
            MediaType.AUDIO,
        )
        result = organizer._resolve_folder_name(file, chat_map)
        assert result == Path("Group 15558888888-12345678/Audio/AUD-20240101-WA0003.opus")

    def test_unmatched_goes_to_unmatched_dir(self, organizer: Organizer, chat_map: dict[str, Chat]):
        file = (
            organizer.media_dir / "WhatsApp Images" / "unmatched-file.png",
            MediaType.IMAGES,
        )
        result = organizer._resolve_folder_name(file, chat_map)
        assert result == Path("Unmatched/Images/unmatched-file.png")
        assert organizer.unmatched == 1

    def test_sanitizes_folder_names(self, organizer: Organizer):
        file = (Path("test.jpg"), MediaType.IMAGES)
        chat_map: dict[str, Chat] = {
            "test.jpg": GroupChat(
                group_id=ChatId("123"), subject='CON "Forbidden / folder <name> ? \0."'
            )
        }
        result = organizer._resolve_folder_name(file, chat_map)
        folder_name = result.name
        assert not re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$", folder_name)
        assert not re.match(r'[<>:"/\\|?*\x00-\x1F]', folder_name)
        assert not folder_name.startswith((".", "-"))
        assert not folder_name.endswith((".", " "))


class TestOrganizerRun:
    def test_dry_run_no_side_effects(self, organizer: Organizer):
        organizer.dry_run = True
        organizer.run()
        assert not organizer.out_dir.exists()

    def test_copy_mode(self, organizer: Organizer):
        organizer.run()
        assert organizer.out_dir.exists()
        assert organizer.processed > 0

    def test_move_mode(self, organizer: Organizer):
        organizer.copy = False
        media_before = len(list(organizer.media_dir.rglob("*")))
        organizer.run()
        media_after = len(list(organizer.media_dir.rglob("*")))
        assert media_after < media_before
        assert organizer.processed > 0

    def test_with_contacts(self, organizer: Organizer, contacts):
        organizer.contacts = contacts
        organizer.run()
        assert (organizer.out_dir / "John Doe").exists()


class TestOrganizerIntegration:
    def test_organizes_files_by_chat(self, organizer: Organizer):
        organizer.run()
        assert organizer.out_dir.exists()
        output_files = [f for f in organizer.out_dir.rglob("*") if f.is_file()]
        assert len(output_files) == organizer.processed

    def test_uses_contact_names(self, organizer: Organizer, contacts):
        organizer.contacts = contacts
        organizer.run()
        assert (organizer.out_dir / "John Doe").exists()
        assert (organizer.out_dir / "Group Name").exists()
