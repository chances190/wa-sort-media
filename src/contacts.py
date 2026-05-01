from __future__ import annotations

import re
import sqlite3
import quopri
from pathlib import Path
from contextlib import closing


# ---------------------------------------------------------------------------
# wa.db loader
# ---------------------------------------------------------------------------


def load_wa_contacts(path: Path) -> dict[str, str]:
    """Load contacts from WhatsApp wa.db. Returns {jid: display_name}."""

    if not path.exists():
        raise FileNotFoundError(f"wa.db not found: {path}")

    with closing(sqlite3.connect(str(path))) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='wa_contacts'")
        if cur.fetchone() is None:
            raise ValueError(
                "'wa_contacts' table not found. Use a VCF export with --contacts instead."
            )

        mapping: dict[str, str] = {}
        cur.execute(
            "SELECT jid, display_name, wa_name, given_name, family_name, number FROM wa_contacts"
        )
        for jid, display_name, wa_name, given_name, family_name in cur.fetchall():
            name = display_name or wa_name or " ".join(filter(None, [given_name, family_name]))
            if name and jid:
                mapping[str(jid)] = str(name).strip()

    if not mapping:
        raise ValueError("'wa_contacts' table is empty.")

    return mapping


# ---------------------------------------------------------------------------
# VCF loader
# ---------------------------------------------------------------------------


def load_vcf_contacts(path: Path) -> dict[str, str]:
    """Load contacts from a VCF file. Returns {jid: display_name}."""

    if not path.exists():
        raise FileNotFoundError(f"Contacts file not found: {path}")

    mapping: dict[str, str] = {}

    for vcard_text in path.read_text(encoding="utf-8", errors="replace").split("BEGIN:VCARD")[1:]:
        name, phones = _parse_vcard_entry(vcard_text)
        for phone in phones:
            for variant in _get_jid_phone_variants(phone):
                if variant not in mapping:
                    mapping[variant] = name

    if not mapping:
        raise ValueError(f"No contacts with phone numbers found in {path}")

    return mapping


def _parse_vcard_entry(text: str) -> tuple[str, list[str]]:
    """Parse a single vCard entry. Returns (display_name, [phone_numbers])."""
    lines = text.splitlines()
    name = ""
    phones: list[str] = []

    i = 0
    while i < len(lines):
        raw_line = lines[i]
        # Handle line folding
        while i + 1 < len(lines) and lines[i + 1] and lines[i + 1][0] in (" ", "\t"):
            i += 1
            raw_line += lines[i].lstrip()

        line = raw_line.strip().upper()

        if line.startswith("FN"):
            _, name = line.split(":", 1)
            if name:
                if "QUOTED-PRINTABLE" in name:
                    try:
                        name_bytes = name.encode("ascii")
                        name = quopri.decodestring(name_bytes).decode("utf-8", errors="replace")
                    except Exception:
                        pass
                name = name.strip()

        elif line.startswith("TEL"):
            _, number = line.split(":", 1)
            if number:
                phones.append(re.sub(r"\D", "", number))

        i += 1

    return name, phones


def _get_jid_phone_variants(phone: str) -> set[str]:
    """Given a raw phone string, return all possible JID digit-forms."""

    variants = {phone}

    # Brazil (+55): WhatsApp sometimes omits the mobile 9 prefix
    if phone.startswith("55"):
        if len(phone) == 13:
            variants.add(phone[:4] + phone[5:])  # strip 9
        elif len(phone) == 12:
            variants.add(phone[:4] + "9" + phone[4:])  # add 9

    # Add other country-specific normalizations here as needed

    return variants
