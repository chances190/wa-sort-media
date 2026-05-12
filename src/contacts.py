import re
import sqlite3
import quopri
from pathlib import Path
from contextlib import closing

from .datatypes import ChatId, DisplayName, Contacts


# ---------------------------------------------------------------------------
# wa.db loader
# ---------------------------------------------------------------------------


def load_wa_contacts(path: Path) -> Contacts:
    """Load contacts from WhatsApp wa.db."""

    if not path.exists():
        raise FileNotFoundError(f"wa.db not found: {path}")

    with closing(sqlite3.connect(str(path))) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT jid, display_name, wa_name
                FROM wa_contacts
            """)
        except sqlite3.OperationalError as e:
            raise ValueError("Invalid wa.db file. Use a VCF export with --contacts instead.") from e

        contacts: Contacts = {}
        for jid, display_name, wa_name in cur:
            raw_name = display_name or wa_name
            if raw_name is not None:
                raw_name = str(raw_name).strip()
            if raw_name and jid:
                chat_id = str(jid).split("@", 1)[0]
                name = str(raw_name).strip()
                contacts[ChatId(chat_id)] = DisplayName(name)

    if not contacts:
        raise ValueError("'wa_contacts' table is empty.")

    return contacts


# ---------------------------------------------------------------------------
# VCF loader
# ---------------------------------------------------------------------------


class PhoneNumber(str):
    def __new__(cls, raw: str | int):
        digits = re.sub(r"\D", "", str(raw))
        return super().__new__(cls, digits)

    def __repr__(self) -> str:
        return f"PhoneNumber(+{super().__str__()})"


def load_vcf_contacts(path: Path) -> Contacts:
    """Load contacts from a VCF file."""

    if not path.exists():
        raise FileNotFoundError(f"Contacts file not found: {path}")

    contacts: Contacts = {}

    for vcard_text in path.read_text(encoding="utf-8", errors="replace").split("BEGIN:VCARD")[1:]:
        name, phones = _parse_vcard_entry(vcard_text)
        for phone in phones:
            contacts.setdefault(ChatId(phone), name)

    if not contacts:
        raise ValueError(f"No contacts with phone numbers found in {path}")

    return contacts


def _parse_vcard_entry(text: str) -> tuple[DisplayName, set[PhoneNumber]]:
    """Parse a single vCard entry."""
    lines = text.splitlines()
    phones: set[PhoneNumber] = set()
    i = 0
    while i < len(lines):
        raw_line = lines[i]
        # Handle line folding
        while i + 1 < len(lines) and lines[i + 1] and lines[i + 1][0] in (" ", "\t"):
            i += 1
            raw_line += lines[i].lstrip()

        line = str(raw_line.strip().casefold())

        if line.startswith("fn"):
            header, name = line.split(":", 1)
            if name:
                if "quoted-printable" in header:
                    try:
                        name_bytes = name.encode("utf-8")
                        name = quopri.decodestring(name_bytes).decode("utf-8", errors="replace")
                    except Exception:
                        pass
                name = name.strip().title()

        elif line.startswith("tel"):
            _, tel = line.split(":", 1)
            if tel:
                variants = _get_all_jid_formats(PhoneNumber(tel))
                phones.update(variants)

        i += 1

    return DisplayName(name), phones


def _get_all_jid_formats(original: PhoneNumber) -> set[PhoneNumber]:
    """Given a phone number, returns all possible ways WhatsApp might store it."""

    variants = {original}

    # Brazil (+55): WhatsApp sometimes omits the mobile 9 prefix
    if original.startswith("55"):
        if len(original) == 13:
            variants.add(PhoneNumber(original[:4] + original[5:]))  # strip 9
        elif len(original) == 12:
            variants.add(PhoneNumber(original[:4] + "9" + original[4:]))  # add 9

    # Add other country-specific normalizations here as needed

    return variants
