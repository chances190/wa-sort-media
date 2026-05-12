"""Tests for the main CLI module."""

import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.main import main


class TestMainCLI:
    def test_help_flag(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Organize WhatsApp media files" in captured.out

    def test_missing_required_args(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code != 0

    def test_basic_args(self, db: Path, media_dir: Path, caplog):
        caplog.set_level(logging.DEBUG)
        with patch("src.main.Organizer") as MockOrganizer:
            mock_organizer = MagicMock()
            MockOrganizer.return_value = mock_organizer
            result = main([str(db), str(media_dir), "--dry-run", "-v"])
            assert result == 0
            call_args = MockOrganizer.call_args[1]
            assert call_args["db_path"] == db
            assert call_args["media_dir"] == media_dir
            assert call_args["dry_run"] is True
            mock_organizer.run.assert_called_once()

    def test_custom_output_dir(self, tmp_path: Path, db: Path, media_dir: Path):
        output_dir = tmp_path / "custom_output"
        with patch("src.main.Organizer") as MockOrganizer:
            mock_organizer = MagicMock()
            MockOrganizer.return_value = mock_organizer
            result = main([str(db), str(media_dir), str(output_dir), "--dry-run"])
            assert result == 0
            assert MockOrganizer.call_args[1]["out_dir"] == output_dir

    def test_move_mode(self, db: Path, media_dir: Path):
        with patch("src.main.Organizer") as MockOrganizer:
            mock_organizer = MagicMock()
            MockOrganizer.return_value = mock_organizer
            result = main([str(db), str(media_dir), "--move", "--dry-run"])
            assert result == 0
            assert MockOrganizer.call_args[1]["copy"] is False

    def test_vcf_contacts(self, db: Path, media_dir: Path, vcf_file: Path):
        with patch("src.main.Organizer") as MockOrganizer:
            mock_organizer = MagicMock()
            MockOrganizer.return_value = mock_organizer
            result = main([str(db), str(media_dir), f"--vcf={str(vcf_file)}", "--dry-run"])
            assert result == 0
            assert MockOrganizer.call_args[1]["contacts"] is not None

    def test_wa_contacts(self, db: Path, media_dir: Path, wa_db: Path):
        with patch("src.main.Organizer") as MockOrganizer:
            mock_organizer = MagicMock()
            MockOrganizer.return_value = mock_organizer
            result = main([str(db), str(media_dir), f"--wa-db={str(wa_db)}", "--dry-run"])
            assert result == 0
            assert MockOrganizer.call_args[1]["contacts"] is not None

    def test_handles_exception(self, db: Path, media_dir: Path):
        with patch("src.main.Organizer") as MockOrganizer:
            mock_organizer = MagicMock()
            MockOrganizer.return_value = mock_organizer
            mock_organizer.run.side_effect = Exception("Test error")
            result = main([str(db), str(media_dir), "--dry-run"])
            assert result != 0


class TestMainEdgeCases:
    def test_nonexistent_database(self, tmp_path: Path, media_dir: Path):
        non_existent = tmp_path / "nonexistent.db"
        result = main([str(non_existent), str(media_dir), "--dry-run"])
        assert result != 0

    def test_nonexistent_media_dir(self, tmp_path: Path, db: Path):
        non_existent = tmp_path / "nonexistent_media"
        result = main([str(db), str(non_existent), "--dry-run"])
        assert result != 0

    def test_special_characters_in_path(self, tmp_path: Path, db: Path, media_dir: Path):
        special_dir = tmp_path / "path with spaces & special [chars]"
        with patch("src.main.Organizer") as MockOrganizer:
            mock_organizer = MagicMock()
            MockOrganizer.return_value = mock_organizer
            result = main([str(db), str(media_dir), str(special_dir), "--dry-run"])
            assert result == 0
