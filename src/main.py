"""CLI entrypoint for the WhatsApp media organizer.

Usage examples:
  wasortmedia msgstore.db "WhatsApp/Media" --wa-db wa.db --dry-run
  wasortmedia msgstore.db "WhatsApp/Media" --contacts contacts.vcf --dry-run
"""

from __future__ import annotations

import argparse
from pathlib import Path
# no extra stdlib imports required

from .contacts import WaDbContacts, VCardContacts
from .organizer import organize_files
from .tui import BrailleMultiProgress


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Organize WhatsApp media files by conversation using msgstore DB"
    )
    p.add_argument("msgstore", help="Path to unlocked msgstore SQLite DB")
    p.add_argument("media", help="Path to WhatsApp Media folder (root) to scan")
    p.add_argument(
        "out", nargs="?", default=None, help="Output root directory (defaults to <media>_organized)"
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Do a dry run and don't copy/move files",
    )
    p.add_argument("-v", "--verbose", action="store_true")

    group = p.add_mutually_exclusive_group()
    group.add_argument("-m", "--move", action="store_true", help="Move files")
    group.add_argument("-c", "--copy", action="store_true", help="Copy files (default)")

    cg = p.add_mutually_exclusive_group()
    cg.add_argument("--wa-db", help="Path to wa.db contacts DB")
    cg.add_argument("--contacts", help="Path to Google Contacts .vcf export")

    args = p.parse_args(argv)

    db_path = Path(args.msgstore)
    media_root = Path(args.media)
    out_root = Path(args.out) if args.out else Path(str(media_root) + "_organized")

    if not db_path.exists():
        print(f"DB not found: {db_path}")
        return 2
    if not media_root.exists():
        print(f"Media folder not found: {media_root}")
        return 2

    dry_run = args.dry_run
    do_move = args.move
    verbose = args.verbose
    # default behavior: copy if neither specified
    if not args.move and not args.copy:
        do_move = False

    if verbose:
        print(
            f"DB: {db_path}\nMedia: {media_root}\nOut: {out_root}\nDry-run: {dry_run}\nMove: {do_move}"
        )

    contacts_map: dict[str, str] | None = None

    if args.wa_db:
        if verbose:
            print(f"Contacts: wa.db -> {args.wa_db}")
        try:
            w = WaDbContacts(Path(args.wa_db), verbose=verbose)
            contacts_map = w.load()
        except ValueError as e:
            print(f"Error with wa.db: {e}")
            return 2
    elif args.contacts:
        if verbose:
            print(f"Contacts: file -> {args.contacts}")
        try:
            v = VCardContacts(Path(args.contacts), verbose=verbose)
            contacts_map = v.load()
        except ValueError as e:
            print(f"Contacts file error: {e}")
            return 2
    else:
        if verbose:
            print("Contacts: none (falling back to phone numbers)")

    ret = organize_files(
        db_path,
        media_root,
        out_root,
        contacts_map,
        dry_run=dry_run,
        do_move=do_move,
        verbose=verbose,
        tui=BrailleMultiProgress() if not verbose else None,
    )
    print(f"Done. Processed {ret} files{' (dry-run)' if dry_run else ''}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
