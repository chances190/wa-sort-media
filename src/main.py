"""CLI entrypoint for the WhatsApp media organizer."""

from __future__ import annotations
from src.datatypes import ChatId, DisplayName

import argparse
import logging
from pathlib import Path

from .contacts import load_wa_contacts, load_vcf_contacts
from .organizer import Organizer


logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Organize WhatsApp media files by conversation")
    p.add_argument("msgstore", help="Path to msgstore.db")
    p.add_argument("media", help="Path to WhatsApp Media folder")
    p.add_argument(
        "out", nargs="?", default=None, help="Output directory (default: <media>_organized)"
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without copying/moving"
    )
    p.add_argument("--move", action="store_true", help="Move files instead of copying")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    cg = p.add_mutually_exclusive_group()
    cg.add_argument("--wa-db", help="Path to wa.db for contact names")
    cg.add_argument("--vcf", help="Path to VCF contacts export")

    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    db_path = Path(args.msgstore)
    media_dir = Path(args.media)
    out_dir = Path(args.out) if args.out else Path(f"{args.media}_organized")

    if not db_path.exists():
        logger.error("msgstore.db not found: %s", db_path)
        return 2
    if not media_dir.exists():
        logger.error("Media folder not found: %s", media_dir)
        return 2

    logger.debug("Using msgstore: %s", db_path)
    logger.debug("Using media directory: %s", media_dir)
    logger.debug("Using output directory: %s", out_dir)
    logger.debug("Mode: %s", "move" if args.move else "copy")
    logger.debug("Dry run: %s", args.dry_run)

    # Load contacts if requested
    contacts: dict[ChatId, DisplayName] | None = None
    if args.wa_db:
        try:
            contacts = load_wa_contacts(Path(args.wa_db))
            logger.debug("Loaded contacts from wa.db: %s", args.wa_db)
        except (FileNotFoundError, ValueError) as e:
            logger.error("Error loading wa.db: %s", e)
            return 2
    elif args.vcf:
        try:
            contacts = load_vcf_contacts(Path(args.vcf))
            logger.debug("Loaded contacts from file: %s", args.vcf)
        except (FileNotFoundError, ValueError) as e:
            logger.error("Error loading contacts file: %s", e)
            return 2

    organizer = Organizer(
        db_path=db_path,
        media_dir=media_dir,
        out_dir=out_dir,
        contacts=contacts,
        dry_run=args.dry_run,
        copy=(not args.move),
    )
    try:
        organizer.run()
    except FileNotFoundError as e:
        logger.error("Error: %s", e)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
