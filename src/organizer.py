"""Organizer: move/copy media files into conversation folders based on msgstore DB."""

from __future__ import annotations

import shutil
import csv
from pathlib import Path
from contextlib import contextmanager
from collections.abc import Iterator
from typing import TextIO

from .db import build_db_map, lookup_chat_name
from .tui import BrailleMultiProgress

# WhatsApp category folders
WA_FOLDER_NAMES = {
    "WhatsApp Images",
    "WhatsApp Video",
    "WhatsApp Video Notes",
    "WhatsApp Audio",
    "WhatsApp Voice Notes",
    "WhatsApp Documents",
    "WhatsApp Animated Gifs",
    "WhatsApp Stickers",
}


def get_category(src: Path, media_root: Path) -> str:
    """Extract category from first folder after media_root."""
    try:
        first_folder = src.relative_to(media_root).parts[0]
        return (
            first_folder.removeprefix("WhatsApp ") if first_folder in WA_FOLDER_NAMES else "Other"
        )
    except (ValueError, IndexError):
        return "Other"


def ensure_unique_path(dest_dir: Path, filename: str) -> Path:
    """Find a unique path by appending _1, _2, etc if needed."""
    dest = dest_dir / filename
    if not dest.exists():
        return dest

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    for i in range(1, 10000):
        candidate = dest_dir / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Could not find unique path for {filename}")


@contextmanager
def open_manifest(out_manifest: Path) -> Iterator[tuple[csv.DictWriter[str], TextIO]]:
    """Open manifest file for appending, write header if new."""
    first_run = not out_manifest.exists()
    file = open(out_manifest, "a", encoding="utf-8", newline="")
    try:
        writer: csv.DictWriter[str] = csv.DictWriter(
            file, fieldnames=["source", "dest", "message_row_id", "chat_row_id", "chat_name"]
        )
        if first_run:
            writer.writeheader()
        yield writer, file
    finally:
        file.close()


def load_already_processed(out_manifest: Path) -> set[str]:
    """Load set of already-processed source paths from manifest."""
    if not out_manifest.exists():
        return set()

    with open(out_manifest, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return {row["source"] for row in reader if row.get("source")}


def scan_files(media_root: Path) -> tuple[list[Path], dict[str, int]]:
    """Scan media folder and return list of files + category counts."""
    all_files: list[Path] = []
    cat_totals: dict[str, int] = {}

    for src in media_root.rglob("*"):
        if src.is_file():
            all_files.append(src)
            cat = get_category(src, media_root)
            cat_totals[cat] = cat_totals.get(cat, 0) + 1

    return all_files, cat_totals


def count_done_per_category(already_processed: set[str], media_root: Path) -> dict[str, int]:
    """Count how many already-processed files exist per category."""
    done_per_cat: dict[str, int] = {}
    for src_str in already_processed:
        cat = get_category(Path(src_str), media_root)
        done_per_cat[cat] = done_per_cat.get(cat, 0) + 1
    return done_per_cat


def resolve_chat_info(
    basename: str,
    mapping: dict[str, list[tuple[int, int | None, str | None, int | None, str | None]]],
    db_path: Path,
    contacts_map: dict[str, str] | None,
    verbose: bool,
) -> tuple[int | None, int | None, str]:
    """Resolve message_id, chat_id, and chat_name for a file."""
    matches = mapping.get(basename, [])

    if not matches:
        return None, None, "unknown"

    if len(matches) == 1:
        msg_id, chat_id, *_ = matches[0]
    else:
        # Prefer matches with chat_row_id
        msg_id, chat_id = None, None
        for mid, cid, *_ in matches:
            if cid:
                msg_id, chat_id = mid, cid
                break

        if chat_id is None:
            # Ambiguous - pick first and warn
            msg_id, chat_id, *_ = matches[0]
            if verbose:
                print(f"Warning: multiple DB entries for {basename}; picking first: chat {chat_id}")

    chat_name = (
        lookup_chat_name(db_path, chat_id, contacts_map=contacts_map, verbose=verbose)
        if chat_id is not None
        else "unknown"
    )

    return msg_id, chat_id, chat_name


def organize_files(
    db_path: Path,
    media_root: Path,
    out_root: Path,
    contacts_map: dict[str, str] | None = None,
    *,
    dry_run: bool = True,
    do_move: bool = False,
    verbose: bool = False,
    tui: BrailleMultiProgress | None = None,
) -> int:
    """Organize media files into chat-based folders."""
    mapping = build_db_map(db_path)
    out_manifest = out_root / "wasort_manifest.csv"

    # Load resume state
    already_processed: set[str] = load_already_processed(out_manifest) if not dry_run else set()
    if verbose and already_processed:
        print(f"Found {len(already_processed)} already-processed files in manifest")

    # Scan media folder
    print("Scanning Media folder...")
    all_files, cat_totals = scan_files(media_root)
    print(f"Found {sum(cat_totals.values())} media files.")

    # Count already-done per category
    already_done_per_cat = count_done_per_category(already_processed, media_root)

    if verbose:
        for cat, count in cat_totals.items():
            if count > 0:
                done = already_done_per_cat.get(cat, 0)
                print(
                    f"  {cat}: {count} total ({count - done} remaining, {done} already processed)"
                )

    # Initialize TUI
    if tui:
        tui.start({k: v for k, v in cat_totals.items() if v > 0})
        for cat, done_count in already_done_per_cat.items():
            if cat in cat_totals and done_count > 0:
                tui.update(cat, done_count)

    # Process files
    processed_per_cat = {k: already_done_per_cat.get(k, 0) for k in cat_totals}
    total_new = 0
    skipped = 0

    def process_file(src: Path, writer: csv.DictWriter[str] | None, file: TextIO | None) -> None:
        """Process a single file - nested function to access outer scope."""
        nonlocal total_new, skipped

        if str(src) in already_processed:
            if verbose:
                print(f"Skipping (already processed): {src}")
            skipped += 1
            return

        total_new += 1
        cat = get_category(src, media_root)
        msg_id, chat_id, chat_name = resolve_chat_info(
            src.name, mapping, db_path, contacts_map, verbose
        )

        dest_dir = out_root / chat_name / cat
        dest_path = dest_dir / src.name

        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = ensure_unique_path(dest_dir, src.name)

            if do_move:
                shutil.move(str(src), str(dest_path))
            else:
                shutil.copy2(str(src), str(dest_path))

            # Write to manifest
            if writer and file:
                writer.writerow(
                    {
                        "source": str(src),
                        "dest": str(dest_path),
                        "message_row_id": str(msg_id) if msg_id is not None else "",
                        "chat_row_id": str(chat_id) if chat_id is not None else "",
                        "chat_name": chat_name,
                    }
                )
                file.flush()

        if verbose:
            print(f"{src} -> {dest_path} (chat_id={chat_id}, name={chat_name})")

        # Update TUI
        processed_per_cat[cat] += 1
        if tui:
            tui.update(cat, processed_per_cat[cat])

    # Main processing loop
    if dry_run:
        for src in all_files:
            process_file(src, None, None)
    else:
        out_root.mkdir(parents=True, exist_ok=True)
        with open_manifest(out_manifest) as (writer, file):
            for src in all_files:
                process_file(src, writer, file)

    if tui:
        tui.finish()

    if verbose:
        print(f"Processed {total_new} new files, skipped {skipped} already-processed files")
        if not dry_run:
            print(f"Manifest written to: {out_manifest}")

    return total_new
