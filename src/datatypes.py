# datatypes.py

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import NewType, TypeAlias

ChatId = NewType("ChatId", str)  # Prefix of the chat's JID (before the @)
DisplayName = NewType("DisplayName", str)
Contacts: TypeAlias = dict[ChatId, DisplayName]


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
            top_folder = src.relative_to(media_root).parts[0]
        except (ValueError, IndexError):
            return cls.OTHER
        folder_name = top_folder.removeprefix("WhatsApp ")
        for category in cls:
            if category.value == folder_name:
                return category
        return cls.OTHER


@dataclass(slots=True)
class DmChat:
    """A media file matched to a 1-on-1 chat."""

    user_id: ChatId  # phone number digits or username


@dataclass(slots=True)
class GroupChat:
    """A media file matched to a group chat."""

    group_id: ChatId  # creator's phone number digits and timestamp
    subject: str | None  # group name from chat.subject


# A match is either a chat or a group, never both
Chat = DmChat | GroupChat


@dataclass(slots=True)
class ResolvedMedia:
    """A file ready to be moved, with its destination fully resolved."""

    source: Path
    dest: Path
