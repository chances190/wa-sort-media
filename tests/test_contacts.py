"""Tests for the contacts module."""

from pathlib import Path

import pytest

from src.contacts import (
    PhoneNumber,
    load_wa_contacts,
    load_vcf_contacts,
    _parse_vcard_entry,
    _get_all_jid_formats,
)
from src.datatypes import ChatId


class TestPhoneNumber:
    def test_creation_normalizes_formats(self):
        expected = "15551234567"
        for number in ["+15551234567", "+1 (555) 123-4567", "15551234567", 15551234567]:
            assert PhoneNumber(number) == expected


class TestGetAllJidFormats:
    def test_brazil_with_9_digit(self):
        phone = PhoneNumber("+55 (11) 9 1234-5678")
        variants = _get_all_jid_formats(phone)
        assert phone in variants
        assert PhoneNumber("+55 (11) 1234-5678") in variants

    def test_brazil_without_9_digit(self):
        phone = PhoneNumber("+55 (11) 1234-5678")
        variants = _get_all_jid_formats(phone)
        assert phone in variants
        assert PhoneNumber("+55 (11) 9 1234-5678") in variants


class TestParseVcardEntry:
    def test_basic_parsing(self):
        vcard_text = """FN:John Doe
TEL;TYPE=CELL:+15551234567
TEL;TYPE=WORK:+15551234567
END:VCARD"""
        name, phones = _parse_vcard_entry(vcard_text)
        assert name == "John Doe"
        assert PhoneNumber("+15551234567") in phones
        assert PhoneNumber("+15551234567") in phones

    def test_quoted_printable(self):
        vcard_text = """FN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:=4A=6F=68=6E=20=44=6F=65
TEL;TYPE=CELL:+15551234567
END:VCARD"""
        name, phones = _parse_vcard_entry(vcard_text)
        assert name == "John Doe"
        assert PhoneNumber("+15551234567") in phones

    def test_line_folding(self):
        vcard_text = """FN:John 
  Doe
TEL;TYPE=CELL:+1555123
  4567
END:VCARD"""
        name, phones = _parse_vcard_entry(vcard_text)
        assert name == "John Doe"
        assert PhoneNumber("+15551234567") in phones


class TestLoadVcfContacts:
    def test_loads_vcf_file(self, vcf_file: Path):
        contacts = load_vcf_contacts(vcf_file)
        assert len(contacts) == 4
        assert contacts[ChatId(PhoneNumber("+15559999999"))] == "John Doe"
        assert contacts[ChatId(PhoneNumber("+15558888888"))] == "Jane Doe"
        assert contacts[ChatId(PhoneNumber("+15557777777"))] == "Jane Doe"
        assert contacts[ChatId(PhoneNumber("+15556666666"))] == "John Smith"

    def test_missing_file(self, tmp_path: Path):
        non_existent = tmp_path / "nonexistent.vcf"
        with pytest.raises(FileNotFoundError):
            load_vcf_contacts(non_existent)


class TestLoadWaContacts:
    def test_loads_wa_db(self, wa_db: Path):
        contacts = load_wa_contacts(wa_db)
        assert contacts[ChatId("15559999999")] == "John Doe"
        assert contacts[ChatId("15558888888")] == "JaneDoeUsername"
        assert contacts.get(ChatId("15557777777")) is None

    def test_missing_file(self, tmp_path: Path):
        non_existent = tmp_path / "nonexistent.db"
        with pytest.raises(FileNotFoundError):
            load_wa_contacts(non_existent)

    def test_missing_table(self, wa_db_without_contacts: Path):
        with pytest.raises(ValueError):
            load_wa_contacts(wa_db_without_contacts)
