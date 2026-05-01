# datatypes.py

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class MediaType(Enum):
    IMAGES = "Images"
    VIDEO = "Video"
    VIDEO_NOTES = "Video Notes"
    AUDIO = "Audio"
    VOICE_NOTES = "Voice Notes"
    DOCUMENTS = "Documents"
    ANIMATED_GIFS = "Animated Gifs"
    STICKERS = "Stickers"
    OTHER = "Other"

    @classmethod
    def from_path(cls, src: Path, media_root: Path) -> MediaType:
        try:
            first_folder = src.relative_to(media_root).parts[0]
        except (ValueError, IndexError):
            return cls.OTHER
        folder_name = first_folder.removeprefix("WhatsApp ")
        for category in cls:
            if category.value == folder_name:
                return category
        return cls.OTHER


@dataclass(slots=True)
class ChatMatch:
    """A media file matched to a 1-on-1 chat."""

    jid_user: str  # phone number or username (without @server)


@dataclass(slots=True)
class GroupMatch:
    """A media file matched to a group chat."""

    jid_user: str  # group id (without @g.us)
    subject: str | None  # group name from chat.subject


# A match is either a chat or a group, never both
Match = ChatMatch | GroupMatch


@dataclass(slots=True)
class ResolvedMedia:
    """A file ready to be moved, with its destination fully resolved."""

    source: Path
    dest: Path
