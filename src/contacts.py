"""Contacts loading utilities.

Provides:
- WaDbContacts: strict loader from wa.db requiring 'wa_contacts' table non-empty
- VCardContacts: loader for VCF exports (VCF/VCARD). CSV support intentionally omitted.
"""

from __future__ import annotations

import re
import sqlite3
import quopri
from pathlib import Path
from contextlib import closing


class WaDbContacts:
    """Load contacts mapping from a WhatsApp `wa.db` SQLite file."""

    def __init__(self, path: Path, verbose: bool = False) -> None:
        self.path = path
        self.verbose = verbose

    def load(self) -> dict[str, str]:
        if not self.path.exists():
            raise ValueError(f"wa.db not found: {self.path}")

        with closing(sqlite3.connect(str(self.path))) as conn:
            cur = conn.cursor()

            # Check for the canonical table and require it
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='wa_contacts'")
            if cur.fetchone() is None:
                raise ValueError(
                    "'wa_contacts' table not found in wa.db. Use a Google Contacts export (VCF) via --contacts-file instead."
                )

            mapping: dict[str, str] = {}
            cur.execute(
                "SELECT jid, display_name, wa_name, given_name, family_name, number FROM wa_contacts"
            )

            for jid, display_name, wa_name, given_name, family_name, number in cur.fetchall():
                # Try display_name, then wa_name, then given+family, then number
                name = (
                    display_name
                    or wa_name
                    or " ".join(filter(None, [given_name, family_name]))
                    or number
                )
                if name and jid:
                    mapping[str(jid)] = str(name).strip()

        if not mapping:
            raise ValueError(
                "'wa_contacts' table is present but contains no contacts. "
                "wa-db must be read from WhatsApp's rooted data directory (/data/data/com.whatsapp/...). "
                "If you don't have a rooted device, export your contacts from Google (VCF) and use --contacts-file."
            )

        if self.verbose:
            print(f"Loaded {len(mapping)} contacts from wa_contacts in {self.path}")

        return mapping


class VCardContacts:
    """Parse Google Contacts exports (VCF/VCARD only) into a mapping usable for
    resolving JIDs and phone numbers to display names.
    """

    def __init__(self, path: Path, verbose: bool = False) -> None:
        self.path = path
        self.verbose = verbose

    @staticmethod
    def _gen_normalized_numbers(s: str) -> set[str]:
        """Returns normalized digits-only format to match JIDs.
        Also generates all possible country-specific variations (e.g., Brazil 55 with/without mobile 9).
        """
        digits = re.sub(r"\D", "", s)
        if not digits:
            return set()

        keys = {digits}

        # Brazil (55): mobile numbers have a 9 prefix that WhatsApp may omit
        # Format: +55 81 9 XXXX-XXXX or +55 81 XXXX-XXXX
        if digits.startswith("55"):
            if len(digits) == 13:
                keys.add("55" + digits[2:4] + digits[5:])
            elif len(digits) == 12:
                keys.add("55" + digits[2:4] + "9" + digits[4:])

        return keys

    def load(self) -> dict[str, str]:
        if not self.path.exists():
            raise ValueError(f"Contacts export not found: {self.path}")

        suffix = self.path.suffix.lower()
        if suffix not in (".vcf", ".vcard"):
            raise ValueError("Only VCF/VCARD files are supported for --contacts.")

        mapping: dict[str, str] = {}

        def add_number(name: str, phone: str) -> None:
            for k in self._gen_normalized_numbers(phone):
                if k not in mapping:
                    mapping[k] = name

        text = self.path.read_text(encoding="utf-8", errors="replace")

        # Simple robust vCard parser - split by BEGIN:VCARD
        vcards = text.split("BEGIN:VCARD")

        for idx, vcard_text in enumerate(vcards[1:], start=1):  # Skip first empty split
            try:
                lines = vcard_text.splitlines()
                name = ""
                phones: list[str] = []

                i = 0
                while i < len(lines):
                    # Preserve raw line for folding, then strip for content parsing
                    raw_line = lines[i]

                    # Handle line folding (continuation lines start with space/tab)
                    while i + 1 < len(lines) and lines[i + 1] and lines[i + 1][0] in (" ", "\t"):
                        i += 1
                        raw_line += lines[i].lstrip()

                    line = raw_line.strip()

                    # Parse FN (formatted name)
                    if line.upper().startswith("FN"):
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            value = parts[1]
                            # Handle QUOTED-PRINTABLE encoding (case-insensitive)
                            if "QUOTED-PRINTABLE" in parts[0].upper():
                                try:
                                    value = quopri.decodestring(value.encode("ascii")).decode(
                                        "utf-8", errors="replace"
                                    )
                                except Exception:
                                    pass
                            name = value.strip()

                    # Parse TEL (phone number)
                    elif line.upper().startswith("TEL"):
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            phones.append(parts[1].strip())

                    i += 1

                # Add all phone numbers for this contact
                if name:
                    for phone in phones:
                        add_number(name, phone)
            except Exception as e:
                # Choke on a malformed vCard entry so user sees the offending entry index
                raise ValueError(f"Error parsing contacts export (vCard entry {idx}): {e}")

        if not mapping:
            raise ValueError(
                f"No contacts parsed from {self.path}; ensure the file contains phone numbers."
            )

        unique_contacts: dict[str, list[str]] = {}
        for phone, name in mapping.items():
            if name not in unique_contacts:
                unique_contacts[name] = []
            unique_contacts[name].append(phone)
        print(f"Loaded {len(unique_contacts)} contacts.")
        if self.verbose:
            print(f"Total phone numbers: {len(mapping)}")
            for name in sorted(unique_contacts.keys()):
                print(
                    f"  {name}: {', '.join(unique_contacts[name][:3])}{' ...' if len(unique_contacts[name]) > 3 else ''}"
                )
        return mapping
